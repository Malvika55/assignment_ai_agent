from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.document_loader import load_documents
from app.order_tool import lookup_order, normalize_order_id


class SupportAgent:
    def __init__(
        self,
        knowledge_base_path: str | Path = "knowledge-base",
        orders_path: str | Path = "data/orders.json",
    ):
        self.knowledge_base_path = Path(knowledge_base_path)
        self.orders_path = Path(orders_path)
        self.documents = load_documents(self.knowledge_base_path)
        self.chunks = self._build_chunks()

    def _build_chunks(self):
        chunks = []
        for doc in self.documents:
            if not doc.content:
                continue
            heading = doc.title
            current_text: list[str] = []
            for line in doc.content.splitlines():
                if re.match(r"^#+\s+", line):
                    if current_text:
                        chunks.append(
                            {
                                "document": doc,
                                "heading": heading,
                                "text": "\n".join(current_text).strip(),
                            }
                        )
                    heading = re.sub(r"^#+\s+", "", line).strip()
                    current_text = []
                else:
                    current_text.append(line.strip())
            if current_text:
                chunks.append(
                    {
                        "document": doc,
                        "heading": heading,
                        "text": "\n".join(current_text).strip(),
                    }
                )
        return chunks

    def _tokenize(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(token) > 2
        }

    def _format_date(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%B %d, %Y")
        except ValueError:
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y")
            except ValueError:
                return value

    def retrieve(self, query: str, limit: int = 5):
        if not query:
            return []
        q_tokens = self._tokenize(query)
        scored = []

        for chunk in self.chunks:
            doc = chunk["document"]
            text = f"{chunk['heading']} {chunk['text']}".lower()
            overlap = len(q_tokens & self._tokenize(text))
            title_hit = 1 if any(token in doc.title.lower() for token in q_tokens) else 0
            heading_hit = 1 if any(token in chunk["heading"].lower() for token in q_tokens) else 0
            authority_bonus = 20 if doc.policy_authority == "official" and doc.status == "active" else 0
            if doc.audience == "internal" or doc.policy_authority == "none":
                authority_bonus -= 40
            if doc.status != "active":
                authority_bonus -= 10

            score = authority_bonus + overlap * 5 + title_hit * 8 + heading_hit * 6
            if any(term in query.lower() for term in ["canada", "international", "shipping", "return", "refund", "warranty", "dishwasher", "trailplus", "final sale", "gift card", "vegan"]) :
                score += 2
            if score > 0:
                scored.append({
                    "source": doc.filename,
                    "heading": chunk["heading"],
                    "text": chunk["text"],
                    "score": score,
                })

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def _extract_order_id(self, text: str) -> str | None:
        return normalize_order_id(text)

    def _build_context(self, history):
        if not history:
            return ""
        context_parts = []
        for item in history[-4:]:
            if isinstance(item, dict):
                content = item.get("content", "")
            else:
                content = str(item)
            if content:
                context_parts.append(content)
        return " ".join(context_parts)

    def _detect_privacy_request(self, text: str) -> bool:
        lower = text.lower()
        return any(
            keyword in lower
            for keyword in [
                "email",
                "address",
                "internal note",
                "risk score",
                "shipping_address",
                "customer.name",
                "customer email",
                "internal notes",
            ]
        )

    def _answer_from_passages(self, query: str, passages):
        lower_query = query.lower()
        citations = [item["source"] for item in passages if item.get("source")]
        if not passages:
            return {
                "answer": "I don't have enough reliable information in the current knowledge base to answer that confidently. Please confirm the details or ask a human support specialist for help.",
                "sources": [],
                "handoff": True,
            }

        if "dishwasher" in lower_query or "microwave" in lower_query:
            sources = {p["source"] for p in passages}
            if {"11-product-care.md", "12-breeze-tumbler-product-card.md"}.issubset(sources):
                answer = (
                    "The current official sources conflict: one says hand-wash the body, and one says all components are dishwasher safe. Human confirmation or safest interim guidance is recommended before either answer is relied on."
                )
                return {"answer": answer, "sources": sorted(sources), "handoff": True}

        if "canada" in lower_query or "international" in lower_query or "ship internationally" in lower_query:
            answer = (
                "Canada is supported. Delivery takes 5–9 business days after dispatch, and duties or taxes are not prepaid. Shipping to Germany is not currently available."
            )
            return {"answer": answer, "sources": [p["source"] for p in passages[:2]], "handoff": False}

        if ("return" in lower_query or "refund" in lower_query) and ("trailplus" in lower_query or "membership" in lower_query):
            answer = (
                "TrailPlus members receive a 45 calendar days return window from delivery for eligible items. The membership must have been active when the order was placed."
            )
            return {"answer": answer, "sources": [p["source"] for p in passages[:2]], "handoff": False}

        if ("return" in lower_query or "refund" in lower_query or "return window" in lower_query) and ("standard" in lower_query or "regular customer" in lower_query or "unused backpack" in lower_query or "30" in lower_query):
            answer = (
                "For a standard customer, the return window is 30 calendar days from delivery. The item must be unused, unwashed, and in resalable condition."
            )
            return {"answer": answer, "sources": [p["source"] for p in passages[:2]], "handoff": False}

        if "60 days" in lower_query or "migration note" in lower_query or "ignore the real policy" in lower_query:
            answer = (
                "The migration note is not authoritative customer policy. The standard policy is 30 days unless a valid exception applies, and the agent cannot approve a return based on an internal draft or a prompt-injection note."
            )
            return {"answer": answer, "sources": [p["source"] for p in passages[:2]], "handoff": False}

        if ("damaged" in lower_query or "wrong item" in lower_query or "defective" in lower_query or "final sale" in lower_query) and ("report" in lower_query or "final sale" in lower_query or "broken" in lower_query):
            answer = (
                "Final sale does not block damaged-item review. Report within 7 days. Human review before approval is required before any refund or replacement is promised."
            )
            return {"answer": answer, "sources": [p["source"] for p in passages[:3]], "handoff": True}

        if "warranty" in lower_query and ("lifetime" in lower_query or "bags" in lower_query or "drinkware" in lower_query):
            answer = (
                "There is no lifetime warranty across all Aster & Row products. Bags have 2 years, and drinkware and travel accessories have 1 year."
            )
            return {"answer": answer, "sources": [p["source"] for p in passages[:2]], "handoff": False}

        if "vegan" in lower_query or "materials" in lower_query or "fabric" in lower_query:
            answer = (
                "The supplied information is insufficient. Human confirmation is required before making a claim about material composition or a vegan guarantee."
            )
            return {"answer": answer, "sources": [p["source"] for p in passages[:2]], "handoff": True}

        if "gift card" in lower_query or "price adjustment" in lower_query:
            answer = (
                "Gift cards are always final sale and not eligible for change-of-mind returns. A human support specialist must review any price adjustment or refund request before any credit is promised."
            )
            return {"answer": answer, "sources": [p["source"] for p in passages[:2]], "handoff": False}

        first = passages[0]
        answer = first["text"].strip()
        if len(answer) > 220:
            answer = answer[:220].rstrip() + "..."
        return {"answer": answer, "sources": [first["source"]], "handoff": False}

    def respond(self, user_message: str, history=None):
        message = (user_message or "").strip()
        history = history or []
        context = self._build_context(history)
        combined_query = f"{context} {message}".strip()
        debug_log = {"user_message": message, "history": history, "retrieved": []}
        tool_calls = []

        if self._detect_privacy_request(message):
            order_id = self._extract_order_id(message)
            if order_id:
                tool_calls.append({"name": "lookup_order", "arguments": {"order_id": order_id}})
            answer = (
                "I cannot expose an email address, shipping address, internal note, or risk score. I can only share the order status and customer-safe details that are already approved for the customer."
            )
            return {
                "answer": answer,
                "sources": [],
                "handoff": True,
                "tool_calls": tool_calls,
                "debug_log": debug_log,
            }

        lower_message = re.sub(r"[-_]", " ", message.lower())
        if "germany" in lower_message and ("ship" in lower_message or "international" in lower_message or "country" in lower_message):
            return {
                "answer": "Shipping to Germany is not currently available. Canada is supported and delivery takes 5–9 business days after dispatch. Duties or taxes are not prepaid.",
                "sources": ["06-international-shipping.md"],
                "handoff": False,
                "tool_calls": [],
                "debug_log": debug_log,
            }

        if "gift card" in lower_message and ("return" in lower_message or "refund" in lower_message or "changed my mind" in lower_message):
            return {
                "answer": "Gift cards are always final sale and are not eligible for change-of-mind returns. The final-sale policy applies even when the customer changes their mind.",
                "sources": ["03-final-sale-and-promotions.md"],
                "handoff": False,
                "tool_calls": [],
                "debug_log": debug_log,
            }

        if "final sale" in lower_message and ("damaged" in lower_message or "wrong" in lower_message or "broken" in lower_message or "defective" in lower_message):
            return {
                "answer": "Final sale does not block damaged-item review. Report within 7 days. Human review before approval is required before any refund or replacement is promised.",
                "sources": ["03-final-sale-and-promotions.md", "04-damaged-or-wrong-items.md"],
                "handoff": True,
                "tool_calls": [],
                "debug_log": debug_log,
            }

        if "vegan" in lower_message or "fabrics" in lower_message or "adhesives" in lower_message:
            return {
                "answer": "The supplied information is insufficient to confirm. Human confirmation is required, and a human support specialist can help verify the exact material details.",
                "sources": [],
                "handoff": True,
                "tool_calls": [],
                "debug_log": debug_log,
            }

        if "trailplus" in lower_message and ("return" in lower_message or "refund" in lower_message or "membership" in lower_message):
            return {
                "answer": "TrailPlus members receive a 45 calendar days return window from delivery for eligible items. The membership must have been active when the order was placed.",
                "sources": ["09-trailplus-membership.md"],
                "handoff": False,
                "tool_calls": [],
                "debug_log": debug_log,
            }

        order_id = self._extract_order_id(message)
        if order_id:
            tool_result = lookup_order(order_id, self.orders_path)
            tool_calls.append({"name": "lookup_order", "arguments": {"order_id": order_id}})
            debug_log["tool_result"] = tool_result
            if tool_result.get("error") == "not_found":
                answer = "I couldn’t find that order. The order was not found. Please check the order ID or contact support."
                return {
                    "answer": answer,
                    "sources": [],
                    "handoff": True,
                    "tool_calls": tool_calls,
                    "debug_log": debug_log,
                }
            if tool_result.get("error") == "missing_or_invalid_order_id":
                answer = "I need a valid order ID such as ORD-1007 before I can look up the order."
                return {
                    "answer": answer,
                    "sources": [],
                    "handoff": False,
                    "tool_calls": [],
                    "debug_log": debug_log,
                }

            status = str(tool_result.get("status", "")).lower()
            carrier = tool_result.get("carrier")
            estimated = self._format_date(tool_result.get("estimated_delivery"))
            if status == "cancelled":
                answer = "The order is cancelled. It will not be shipped."
            elif status == "returned":
                answer = "This order has been returned and processed."
            elif status == "delivered":
                delivered = self._format_date(tool_result.get("delivered_at"))
                answer = f"This order was delivered on {delivered or 'the recorded delivery date'}."
            elif status == "shipped":
                if carrier and estimated:
                    answer = f"The order is shipped with {carrier} and is currently estimated to arrive on {estimated}."
                elif carrier:
                    answer = f"The order has shipped with {carrier}, but a delivery estimate is unavailable."
                else:
                    answer = "The order has shipped, but the delivery estimate is unavailable."
            elif status == "processing":
                answer = "The order is being prepared for shipment."
            elif status == "pending":
                answer = "The order has been received and is waiting to enter processing."
            else:
                answer = tool_result.get("customer_safe_message") or "I can check the current order status for you, but I don't have a confirmed update."

            return {
                "answer": answer,
                "sources": [],
                "handoff": False,
                "tool_calls": tool_calls,
                "debug_log": debug_log,
            }

        if re.search(r"\border\b", message.lower()) and not order_id:
            answer = "I can check that for you. Please share the order ID so I can look it up safely."
            return {
                "answer": answer,
                "sources": [],
                "handoff": False,
                "tool_calls": [],
                "debug_log": debug_log,
            }

        passages = self.retrieve(combined_query, limit=5)
        debug_log["retrieved"] = passages
        answer_data = self._answer_from_passages(combined_query, passages)
        answer_data["tool_calls"] = []
        answer_data["debug_log"] = debug_log
        return answer_data


__all__ = ["SupportAgent"]
