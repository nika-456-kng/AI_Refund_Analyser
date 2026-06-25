import os
import re
import faiss
import numpy as np
from datetime import datetime
from sentence_transformers import SentenceTransformer
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any

app = FastAPI()

# Enable CORS so your React frontend can communicate safely with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
# 📝 UPGRADED INTEGRATED AUDIT TRAIL LOGGING ENGINE
# =====================================================================
def init_audit_file():
    """Verifies if the logging ecosystem file exists; creates it with system headers if missing."""
    if not os.path.exists("audit_trail.txt"):
        with open("audit_trail.txt", "w", encoding="utf-8") as f:
            f.write(f"{'='*105}\n")
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] SYSTEM COLD-BOOT INITIALIZED\n")
            f.write(f"{'='*105}\n")
            f.write(f"{'[TIMESTAMP]':<21} {'[ORDER ID]':<10} {'[AGENT MODULE]':<21} {'[STATUS]':<9} [OPERATION DETAILS]\n")
            f.write(f"{'-'*105}\n")

def log_audit_trail(order_id: str, agent_name: str, status: str, action_details: str):
    """Appends a structured, easily parsable corporate log entry to a local file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{order_id:<8}] [{agent_name:<19}] [{status:<7}]: {action_details}\n"
    with open("audit_trail.txt", "a", encoding="utf-8") as f:
        f.write(log_entry)

# Initialize the audit log instantly on backend start up
init_audit_file()

# =====================================================================
# 🛠️ DATABASE & FAISS CORE INITIALIZATION
# =====================================================================
DATABASE_URL = "sqlite:///refund_system.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()

class Order(Base):
    __tablename__ = "orders"
    order_id = Column(String, primary_key=True)
    customer_email = Column(String)
    purchase_date = Column(String)
    amount = Column(Float)
    status = Column(String)
    category = Column(String)

Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Add Mock Rows
session = SessionLocal()
mock_orders = [
    Order(order_id="ORD12345", customer_email="alex@example.com", purchase_date="2026-06-20", amount=120.50, status="Delivered", category="Electronics"),
    Order(order_id="ORD67890", customer_email="sam@example.com", purchase_date="2026-05-11", amount=45.00, status="Delivered", category="Clothing"),
    Order(order_id="ORD55555", customer_email="jesse@example.com", purchase_date="2026-06-23", amount=59.99, status="Delivered", category="Digital Download")
]
for o in mock_orders: session.merge(o)
session.commit()
session.close()

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
company_policies = [
    "Standard Refund Window: Customers can request a full refund for any standard retail product within 30 days of the purchase delivery date.",
    "Damaged or Broken Goods: If an item arrives broken, defective, or damaged, it is eligible for a full refund or immediate replacement regardless of the standard timeline.",
    "Final Sale and Digital Items: All items marked as 'Final Sale' or digital software downloads are strictly non-refundable once purchased.",
    "Tiered Partial Refunds: Items returned between 31 and 60 days after purchase are eligible for a 50% partial store credit refund, subject to management approval."
]
policy_embeddings = embedding_model.encode(company_policies)
faiss_index = faiss.IndexFlatL2(policy_embeddings.shape[1])
faiss_index.add(np.array(policy_embeddings).astype("float32"))

class AgentState(TypedDict):
    user_input: str
    next_step: str
    order_id: str
    order_data: Dict[str, Any]
    policy_data: str
    final_decision: str

# =====================================================================
# 🧠 LANGGRAPH AGENT NODES WITH ACTIVE AUDIT CALLS
# =====================================================================
def supervisor_node(state: AgentState):
    oid = state.get("order_id") if state.get("order_id") else "PENDING"
    
    if not state.get("order_data"):
        found_id = re.search(r"ORD\d+", state["user_input"])
        if found_id: 
            log_audit_trail(found_id.group(0), "Supervisor", "INFO", "Identified tracking pattern token. Routing ticket to Verification.")
            return {"next_step": "validation", "order_id": found_id.group(0)}
        
        log_audit_trail("UNKNOWN", "Supervisor", "WARNING", "No valid tracking ID pattern caught in the input text string.")
        return {"next_step": "end", "final_decision": "Rejected: Missing valid Order ID format."}
    
    if not state.get("policy_data"):
        if state["order_data"]["status"] == "ERROR": 
            log_audit_trail(state["order_id"], "Supervisor", "ERROR", "Database row search reported error. Terminating pipeline.")
            return {"next_step": "end", "final_decision": "Rejected: Order lookup failed."}
        
        if state["order_data"]["category"] == "Digital Download":
            log_audit_trail(state["order_id"], "Supervisor", "BLOCK", "Digital inventory category restriction triggered. Overriding to Reject.")
            return {"next_step": "end", "final_decision": "Subject: Refund Denied\n\nPer company policy section 3, digital software assets are strictly non-refundable once purchased."}
            
        return {"next_step": "policy"}
        
    if not state.get("final_decision"): 
        return {"next_step": "communication"}
        
    return {"next_step": "end"}

def validation_node(state: AgentState):
    db_session = SessionLocal()
    order = db_session.query(Order).filter(Order.order_id == state["order_id"]).first()
    db_session.close()
    if order:
        res = {"status": "SUCCESS", "order_id": order.order_id, "email": order.customer_email, "date": order.purchase_date, "amount": order.amount, "category": order.category}
        log_audit_trail(state["order_id"], "Validation Agent", "SUCCESS", f"Fetched database row. Category: {order.category} | Amount: ${order.amount}")
    else:
        res = {"status": "ERROR"}
        log_audit_trail(state["order_id"], "Validation Agent", "ERROR", "Target Order tracking ID missing from server tables.")
    return {"order_data": res}

def policy_node(state: AgentState):
    query_embedding = embedding_model.encode([state["user_input"]])
    _, indices = faiss_index.search(np.array(query_embedding).astype("float32"), k=1)
    matched_policy = company_policies[indices[0][0]]
    log_audit_trail(state["order_id"], "Policy Agent", "MATCH", f"FAISS context index matched rule clause: '{matched_policy[:35]}...'")
    return {"policy_data": matched_policy}

def communication_node(state: AgentState):
    order, policy = state["order_data"], state["policy_data"]
    days_passed = (datetime.strptime("2026-06-25", "%Y-%m-%d") - datetime.strptime(order["date"], "%Y-%m-%d")).days
    
    if "Damaged or Broken Goods" in policy:
        log_audit_trail(state["order_id"], "Communication Agent", "APPROVE", "Damaged waiver triggered. Overriding standard timeline for Full Refund.")
        body = f"Subject: Full Refund Approved - Order {state['order_id']}\n\nDear Customer,\n\nBecause your item arrived damaged, we have approved a full refund of ${order['amount']} back to your payment account."
    elif days_passed <= 30:
        log_audit_trail(state["order_id"], "Communication Agent", "APPROVE", f"Standard return window valid ({days_passed} days elapsed). Authorizing Full Refund.")
        body = f"Subject: Refund Processed - Order {state['order_id']}\n\nDear Customer,\n\nYour request was submitted within our standard 30-day window. A full refund of ${order['amount']} has been processed."
    elif 31 <= days_passed <= 60:
        log_audit_trail(state["order_id"], "Communication Agent", "PARTIAL", f"Fallback window triggered ({days_passed} days elapsed). Issuing 50% Store Credit.")
        body = f"Subject: Partial Credit Issued - Order {state['order_id']}\n\nDear Customer,\n\nYour request fell within our 60-day threshold. We have issued a 50% partial store credit worth ${round(order['amount']*0.5, 2)}."
    else:
        log_audit_trail(state["order_id"], "Communication Agent", "REJECT", f"Hard temporal boundary breached ({days_passed} days elapsed). Request Denied.")
        body = f"Subject: Refund Update - Order {state['order_id']}\n\nDear Customer,\n\nBecause the transaction transpired over 60 days ago, it has exceeded our tracking threshold limit."
    return {"final_decision": body}

# --- COMPILE STATE GRAPH ---
graph = StateGraph(AgentState)
graph.add_node("supervisor", supervisor_node)
graph.add_node("validation", validation_node)
graph.add_node("policy", policy_node)
graph.add_node("communication", communication_node)
graph.set_entry_point("supervisor")
graph.add_conditional_edges("supervisor", lambda x: x["next_step"], {"validation": "validation", "policy": "policy", "communication": "communication", "end": END})
graph.add_edge("validation", "supervisor")
graph.add_edge("policy", "supervisor")
graph.add_edge("communication", "supervisor")
agent_pipeline = graph.compile()

# --- API ROUTER ENDPOINTS ---
class RefundRequestPayload(BaseModel):
    message: str

@app.post("/api/process-refund")
async def process_refund_endpoint(payload: RefundRequestPayload):
    try:
        initial_state = {"user_input": payload.message, "next_step": "", "order_id": "", "order_data": None, "policy_data": "", "final_decision": ""}
        result = agent_pipeline.invoke(initial_state)
        return {
            "order_id": result.get("order_id"),
            "order_data": result.get("order_data"),
            "policy_data": result.get("policy_data"),
            "final_decision": result.get("final_decision")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)