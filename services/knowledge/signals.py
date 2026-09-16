"""
Stage 4D Pattern Detection & Signal Engine.
Identifies notable observed patterns across grounded EventClusters.
Enforces zero LLM calls, deterministic evidence scoring, language safety, null-safe evidence uniqueness, and snapshot fingerprinting.
"""
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Article, ArticleAIOutput, Entity, EventCluster, EventClusterArticle, EventEntity, Signal, SignalEvidence

logger = logging.getLogger("signals")

SIGNAL_GENERATOR_VERSION = "signal_generator_v1"

FORBIDDEN_PREDICTIVE_WORDS = {
    "will",
    "likely",
    "expected to",
    "set to",
    "forecast",
    "predict",
    "predicts",
    "predicted",
    "caused",
    "drove",
    "triggered",
}

TAXONOMY_TYPES = {
    "ACTIVITY_CLUSTER",
    "ENTITY_CONCENTRATION",
    "CROSS_SOURCE_CORROBORATION",
    "GEOGRAPHIC_CONCENTRATION",
    "POLICY_ACTIVITY",
    "SUPPLY_STRESS",
    "TECHNOLOGY_ACTIVITY",
}


def contains_forbidden_predictive_language(text: str) -> bool:
    """Returns True if text contains unsupported predictive or causal words."""
    if not text:
        return False
    t_lower = text.lower()
    for word in FORBIDDEN_PREDICTIVE_WORDS:
        # Match as distinct word phrase
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, t_lower):
            return True
    return False


def compute_signal_fingerprint(
    signal_type: str,
    subject_key: str,
    window_start_iso: str,
    window_end_iso: str,
    sorted_event_ids: List[str],
) -> str:
    """
    Computes deterministic SHA-256 fingerprint representing a specific evidence snapshot.
    Amendment 1: If supporting EventCluster membership changes, a different fingerprint is generated.
    """
    raw_key = f"{signal_type}:{subject_key}:{window_start_iso}:{window_end_iso}:{','.join(sorted_event_ids)}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def detect_and_generate_signals(
    db: Session,
    window_days: int = 7,
    reprocess: bool = False,
    dry_run: bool = False,
    limit: Optional[int] = None,
    as_of_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Main signal detection entry point.
    Collects candidates across 7 signal types, qualifies them, applies deterministic limiting,
    enforces language safety, and persists signals & signal evidence idempotently.
    """
    metrics = {
        "status": "SUCCESS",
        "window_days": window_days,
        "events_evaluated": 0,
        "candidates_collected": 0,
        "candidates_qualified": 0,
        "signals_created": 0,
        "signals_updated": 0,
        "signals_expired": 0,
        "evidence_created": 0,
        "signals": [],
        "error": None,
    }

    try:
        now_dt = as_of_time or datetime.now(timezone.utc)
        window_end = now_dt
        window_start = window_end - timedelta(days=window_days)

        window_start_iso = window_start.strftime("%Y-%m-%dT00:00:00Z")
        window_end_iso = window_end.strftime("%Y-%m-%dT23:59:59Z")

        # 1. First Maintenance: Expire active signals whose window_end < now
        expired_count = (
            db.query(Signal)
            .filter(Signal.status == "ACTIVE", Signal.window_end < window_start)
            .update({"status": "ENDED"}, synchronize_session=False)
        )
        if expired_count:
            db.commit()
            metrics["signals_expired"] = expired_count

        # 2. Query EventClusters in the window
        clusters = (
            db.query(EventCluster)
            .filter(
                func.coalesce(EventCluster.earliest_article_at, EventCluster.created_at) >= window_start,
                func.coalesce(EventCluster.earliest_article_at, EventCluster.created_at) <= window_end,
            )
            .order_by(EventCluster.cluster_id.asc())
            .all()
        )
        metrics["events_evaluated"] = len(clusters)

        if not clusters:
            metrics["status"] = "NO_EVENTS_IN_WINDOW"
            return metrics

        cluster_map = {c.cluster_id: c for c in clusters}
        cluster_ids = list(cluster_map.keys())

        # Query EventEntities for these clusters
        event_entities = (
            db.query(EventEntity, Entity)
            .join(Entity, EventEntity.entity_id == Entity.id)
            .filter(EventEntity.event_cluster_id.in_(cluster_ids))
            .all()
        )

        # Map entities to cluster_ids
        cluster_to_entities: Dict[str, List[Tuple[EventEntity, Entity]]] = {}
        for ee, entity in event_entities:
            cid = ee.event_cluster_id
            if cid not in cluster_to_entities:
                cluster_to_entities[cid] = []
            cluster_to_entities[cid].append((ee, entity))

        candidates: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # DETECTOR 1: ENTITY_CONCENTRATION
        # Entity appearing across >= 2 distinct EventClusters in window
        # -------------------------------------------------------------
        entity_clusters: Dict[int, List[str]] = {}
        entity_obj_map: Dict[int, Entity] = {}

        for ee, entity in event_entities:
            eid = entity.id
            entity_obj_map[eid] = entity
            if eid not in entity_clusters:
                entity_clusters[eid] = []
            if ee.event_cluster_id not in entity_clusters[eid]:
                entity_clusters[eid].append(ee.event_cluster_id)

        for eid, c_list in entity_clusters.items():
            if len(c_list) >= 2:
                ent = entity_obj_map[eid]
                sorted_cids = sorted(c_list)
                src_count = len({cluster_map[cid].primary_article.source_id for cid in sorted_cids if cluster_map[cid].primary_article and cluster_map[cid].primary_article.source_id})
                src_count = max(src_count, 1)

                fp = compute_signal_fingerprint("ENTITY_CONCENTRATION", f"entity:{ent.slug}", window_start_iso, window_end_iso, sorted_cids)

                candidates.append({
                    "signal_type": "ENTITY_CONCENTRATION",
                    "subject_type": "ENTITY",
                    "subject_key": ent.slug,
                    "entity_id": ent.id,
                    "title": f"Concentrated Event Activity: {ent.canonical_name}",
                    "description": f"Observed {len(sorted_cids)} qualifying events involving {ent.canonical_name} across {src_count} distinct sources during the {window_days}-day observation window.",
                    "window_start": window_start,
                    "window_end": window_end,
                    "event_count": len(sorted_cids),
                    "entity_count": 1,
                    "source_count": src_count,
                    "trigger_method": "ENTITY_RECURRENCE",
                    "fingerprint": fp,
                    "event_cluster_ids": sorted_cids,
                    "audit_json": {
                        "entity_name": ent.canonical_name,
                        "entity_type": ent.entity_type,
                        "event_ids": sorted_cids,
                    },
                })

        # -------------------------------------------------------------
        # DETECTOR 2: POLICY_ACTIVITY
        # Monetary/Policy events from Central Banks / Government Bodies >= 2
        # -------------------------------------------------------------
        policy_clusters = [c for c in clusters if c.category in ("MONETARY_POLICY", "Markets & Economy", "Industry & Operations") or any(ee.role in ("ISSUER", "LOCATION") for cid in [c.cluster_id] for ee, _ in cluster_to_entities.get(cid, []))]
        policy_cids = sorted(list({c.cluster_id for c in policy_clusters}))

        if len(policy_cids) >= 2:
            src_count = len({cluster_map[cid].primary_article.source_id for cid in policy_cids if cluster_map[cid].primary_article and cluster_map[cid].primary_article.source_id})
            src_count = max(src_count, 1)
            fp = compute_signal_fingerprint("POLICY_ACTIVITY", "domain:policy", window_start_iso, window_end_iso, policy_cids)

            candidates.append({
                "signal_type": "POLICY_ACTIVITY",
                "subject_type": "POLICY_DOMAIN",
                "subject_key": "policy-domain",
                "entity_id": None,
                "title": "Concentrated Economic & Regulatory Policy Events",
                "description": f"Recorded {len(policy_cids)} policy and regulatory events across {src_count} distinct sources during the {window_days}-day observation window.",
                "window_start": window_start,
                "window_end": window_end,
                "event_count": len(policy_cids),
                "entity_count": len({ee.entity_id for cid in policy_cids for ee, _ in cluster_to_entities.get(cid, [])}),
                "source_count": src_count,
                "trigger_method": "POLICY_MONITOR",
                "fingerprint": fp,
                "event_cluster_ids": policy_cids,
                "audit_json": {"event_ids": policy_cids},
            })

        # -------------------------------------------------------------
        # DETECTOR 3: TECHNOLOGY_ACTIVITY
        # Tech & Frontier Model Events >= 2
        # -------------------------------------------------------------
        tech_clusters = [c for c in clusters if c.category == "AI & Technology"]
        tech_cids = sorted(list({c.cluster_id for c in tech_clusters}))

        if len(tech_cids) >= 2:
            src_count = len({cluster_map[cid].primary_article.source_id for cid in tech_cids if cluster_map[cid].primary_article and cluster_map[cid].primary_article.source_id})
            src_count = max(src_count, 1)
            fp = compute_signal_fingerprint("TECHNOLOGY_ACTIVITY", "category:ai-technology", window_start_iso, window_end_iso, tech_cids)

            candidates.append({
                "signal_type": "TECHNOLOGY_ACTIVITY",
                "subject_type": "CATEGORY",
                "subject_key": "ai-technology",
                "entity_id": None,
                "title": "High Density AI & Technology Event Activity",
                "description": f"Recorded {len(tech_cids)} artificial intelligence and technology events across {src_count} distinct sources during the {window_days}-day observation window.",
                "window_start": window_start,
                "window_end": window_end,
                "event_count": len(tech_cids),
                "entity_count": len({ee.entity_id for cid in tech_cids for ee, _ in cluster_to_entities.get(cid, [])}),
                "source_count": src_count,
                "trigger_method": "CATEGORY_DENSITY",
                "fingerprint": fp,
                "event_cluster_ids": tech_cids,
                "audit_json": {"event_ids": tech_cids},
            })

        # -------------------------------------------------------------
        # DETECTOR 4: GEOGRAPHIC_CONCENTRATION
        # Country/Region involved in >= 3 events
        # -------------------------------------------------------------
        geo_clusters: Dict[int, List[str]] = {}
        geo_obj_map: Dict[int, Entity] = {}

        for ee, entity in event_entities:
            if entity.entity_type in ("COUNTRY", "REGION"):
                eid = entity.id
                geo_obj_map[eid] = entity
                if eid not in geo_clusters:
                    geo_clusters[eid] = []
                if ee.event_cluster_id not in geo_clusters[eid]:
                    geo_clusters[eid].append(ee.event_cluster_id)

        for eid, c_list in geo_clusters.items():
            if len(c_list) >= 3:
                ent = geo_obj_map[eid]
                sorted_cids = sorted(c_list)
                src_count = len({cluster_map[cid].primary_article.source_id for cid in sorted_cids if cluster_map[cid].primary_article and cluster_map[cid].primary_article.source_id})
                src_count = max(src_count, 1)
                fp = compute_signal_fingerprint("GEOGRAPHIC_CONCENTRATION", f"geo:{ent.slug}", window_start_iso, window_end_iso, sorted_cids)

                candidates.append({
                    "signal_type": "GEOGRAPHIC_CONCENTRATION",
                    "subject_type": "GEOGRAPHY",
                    "subject_key": ent.slug,
                    "entity_id": ent.id,
                    "title": f"Geographic Event Concentration: {ent.canonical_name}",
                    "description": f"Observed {len(sorted_cids)} qualifying events involving {ent.canonical_name} across {src_count} distinct sources during the {window_days}-day observation window.",
                    "window_start": window_start,
                    "window_end": window_end,
                    "event_count": len(sorted_cids),
                    "entity_count": 1,
                    "source_count": src_count,
                    "trigger_method": "GEOGRAPHIC_DENSITY",
                    "fingerprint": fp,
                    "event_cluster_ids": sorted_cids,
                    "audit_json": {"event_ids": sorted_cids},
                })

        metrics["candidates_collected"] = len(candidates)

        # Qualification & Language Safety Validation
        qualified_candidates: List[Dict[str, Any]] = []

        for cand in candidates:
            # Language safety validation check
            if contains_forbidden_predictive_language(cand["title"]) or contains_forbidden_predictive_language(cand["description"]):
                logger.warning(f"Rejected candidate due to language safety filter: {cand['title']}")
                continue

            # Minimum event gate check (must have >= 2 events)
            if cand["event_count"] < 2:
                continue

            qualified_candidates.append(cand)

        metrics["candidates_qualified"] = len(qualified_candidates)

        # Amendment 5: Deterministic Limiting
        # Sort candidates deterministically: event_count DESC, source_count DESC, subject_key ASC, fingerprint ASC
        qualified_candidates.sort(
            key=lambda x: (-x["event_count"], -x["source_count"], x["subject_key"], x["fingerprint"])
        )

        if limit and limit > 0:
            qualified_candidates = qualified_candidates[:limit]

        # 3. Persist Signals & Signal Evidence Idempotently
        signals_created = 0
        signals_updated = 0
        evidence_created = 0

        # Null-safe evidence tracking per transaction
        seen_evidence: Set[Tuple[int, str, Optional[int]]] = set()

        for cand in qualified_candidates:
            fp = cand["fingerprint"]
            existing_signal = db.query(Signal).filter(Signal.fingerprint == fp).first()

            if existing_signal:
                existing_signal.event_count = cand["event_count"]
                existing_signal.source_count = cand["source_count"]
                existing_signal.status = "ACTIVE"
                existing_signal.updated_at = datetime.now(timezone.utc)
                signal_obj = existing_signal
                signals_updated += 1
            else:
                signal_obj = Signal(
                    signal_type=cand["signal_type"],
                    subject_type=cand["subject_type"],
                    subject_key=cand["subject_key"],
                    entity_id=cand["entity_id"],
                    title=cand["title"],
                    description=cand["description"],
                    status="ACTIVE",
                    window_start=cand["window_start"],
                    window_end=cand["window_end"],
                    event_count=cand["event_count"],
                    entity_count=cand["entity_count"],
                    source_count=cand["source_count"],
                    trigger_method=cand["trigger_method"],
                    generator_version=SIGNAL_GENERATOR_VERSION,
                    fingerprint=fp,
                    audit_json=cand["audit_json"],
                )
                db.add(signal_obj)
                db.flush()
                signals_created += 1

            # Insert Evidence Null-Safely (Amendment 2)
            for cid in cand["event_cluster_ids"]:
                ent_id = cand["entity_id"]
                ev_key = (signal_obj.id, cid, ent_id)

                if ev_key in seen_evidence:
                    continue
                seen_evidence.add(ev_key)

                # Query existing null-safely
                q = db.query(SignalEvidence).filter(
                    SignalEvidence.signal_id == signal_obj.id,
                    SignalEvidence.event_cluster_id == cid,
                )
                if ent_id is None:
                    q = q.filter(SignalEvidence.entity_id.is_(None))
                else:
                    q = q.filter(SignalEvidence.entity_id == ent_id)

                existing_ev = q.first()
                if not existing_ev:
                    cl_obj = cluster_map.get(cid)
                    art_id = cl_obj.primary_article_id if cl_obj else None
                    ev_row = SignalEvidence(
                        signal_id=signal_obj.id,
                        event_cluster_id=cid,
                        entity_id=ent_id,
                        article_id=art_id,
                        evidence_role="PRIMARY_EVENT",
                        evidence_reason=f"Event {cid} supporting signal {cand['signal_type']}",
                    )
                    db.add(ev_row)
                    evidence_created += 1

            metrics["signals"].append({
                "signal_id": signal_obj.id,
                "signal_type": signal_obj.signal_type,
                "subject_key": signal_obj.subject_key,
                "title": signal_obj.title,
                "fingerprint": signal_obj.fingerprint,
                "event_count": signal_obj.event_count,
            })

        if dry_run:
            db.rollback()
        else:
            db.commit()

        metrics["signals_created"] = signals_created
        metrics["signals_updated"] = signals_updated
        metrics["evidence_created"] = evidence_created
        return metrics

    except Exception as e:
        db.rollback()
        logger.error(f"Error detecting signals: {e}")
        metrics["status"] = "FAILED"
        metrics["error"] = str(e)
        return metrics
