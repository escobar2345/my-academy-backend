"""YouTube é•œåƒæŽ¨èï¼ˆmirror-fishï¼‰API

æä¾›ï¼š
POST /api/youtube/mirror-fish/best

è¾“å…¥ï¼š
{
  "topic": "...",                // å¿…å¡«
  "section_title": "...",      // å¯é€‰
  "simulation_id": "sim_xxx"  // å¿…å¡«ï¼ˆç”¨äºŽå–æŠ¥å‘Šä¸Žé‡‡è®¿è¯æ®ï¼‰
}

è¾“å‡ºï¼š
{
  "success": true,
  "data": {
    "candidates": [... top3 ...],
    "best_video": { ... }
  }
}

è¯´æ˜Žï¼š
- top3 æ¥è‡ª backend/app/boi-rsu/youtube.py çš„æ•™å­¦è¯„åˆ†ä¸Ž embed_url è¿‡æ»¤
- é€‰æ‹©â€œæœ€ä½³æ•™å­¦è§†é¢‘â€ä¾æ®ï¼š
  1) Report markdownï¼ˆGET /api/report/by-simulation/... å†…éƒ¨è°ƒç”¨ ReportManagerï¼‰
  2) Interviewsï¼ˆå¦‚æŠ¥å‘Šä¸­å·²ç”Ÿæˆï¼Œæˆ–å¯ä»Ž simulation çš„ interview history/æ•°æ®ä¸­è¯»å–ï¼‰

å½“å‰å®žçŽ°ï¼šå…ˆä½¿ç”¨ Report markdown åšä¸»è¯æ®ï¼›å¦‚æžœ interview è¯æ®å¯è¯»å–åˆ™è¿½åŠ ã€‚
"""

import importlib.util
import os
import traceback
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from ..utils.logger import get_logger

logger = get_logger("mirofish.api.youtube_mirror_fish")

youtube_mirror_fish_bp = Blueprint("youtube_mirror_fish", __name__)

def _load_youtube_helper():
    helper_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "boi-rsu", "youtube.py")
    )
    spec = importlib.util.spec_from_file_location("mirofish_boi_rsu_youtube", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load YouTube helper from {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _get_report_markdown(simulation_id: str) -> Optional[Dict[str, Any]]:
    try:
        from app.services.report_agent import ReportManager

        report = ReportManager.get_report_by_simulation(simulation_id)
        if not report:
            return None
        d = report.to_dict()
        d["markdown_preview"] = (d.get("markdown_content") or "")[:12000]
        return d
    except Exception as e:
        logger.warning(f"è¯»å– report å¤±è´¥: {e}")
        return None


def _get_interview_evidence(simulation_id: str) -> Optional[str]:
    """å°½åŠ›èŽ·å– interview history ä½œä¸ºè¯æ®ã€‚

    æœ¬é¡¹ç›® interview åŽ†å²åœ¨ SimulationRunner ç›¸å…³å®žçŽ°é‡Œã€‚
    è‹¥æ— æ³•èŽ·å–ï¼Œåˆ™è¿”å›ž Noneï¼Œä¸å½±å“ä¸»æµç¨‹ã€‚
    """
    try:
        from app.services.simulation_runner import SimulationRunner

        # å–æœ€è¿‘å°‘é‡é‡‡è®¿ä½œä¸ºè¯æ®ï¼ˆlimit=20ï¼‰
        history = SimulationRunner.get_interview_history(
            simulation_id=simulation_id,
            platform=None,
            agent_id=None,
            limit=20,
        )
        if not history:
            return None

        return str(history)[:12000]
    except Exception as e:
        logger.warning(f"è¯»å– interview evidence å¤±è´¥: {e}")
        return None


def _choose_best_by_llm(*, topic: str, section_title: str, simulation_id: str, candidates: List[Dict[str, Any]], report: Dict[str, Any], interview_evidence: Optional[str]) -> Dict[str, Any]:
    from app.utils.llm_client import LLMClient

    llm = LLMClient()

    candidates_brief = []
    for v in candidates:
        candidates_brief.append({
            "rank": v.get("rank"),
            "title": v.get("title"),
            "channel": v.get("channel"),
            "embed_url": v.get("embed_url"),
            "teaching_score": v.get("teaching_score"),
            "why_ranked": v.get("why_ranked"),
            "duration": v.get("duration_display"),
        })

    user_payload = {
        "topic": topic,
        "section_title": section_title,
        "simulation_id": simulation_id,
        "report": {
            "report_id": report.get("report_id"),
            "status": report.get("status"),
            "markdown_preview": report.get("markdown_preview"),
        },
        "interview_evidence": interview_evidence,
        "candidates": candidates_brief,
        "task": "åœ¨3ä¸ªå€™é€‰ä¸­é€‰æ‹©æœ€é€‚åˆç”¨äºŽæ•™å­¦ï¼ˆç«™å†…é•œåƒæ’­æ”¾ï¼‰çš„é‚£ä¸€ä¸ªã€‚è¿”å›žä¸¥æ ¼JSONï¼š{best_index:int(0..2), reason:string, mapping:{title_to_why:string}}"
    }

    system_prompt = (
        "ä½ æ˜¯æ•™å­¦å†…å®¹é€‰æ‹©å™¨ã€‚ä½ å¿…é¡»åŸºäºŽä¸¤ç±»è¯æ®åšåˆ¤æ–­ï¼š"
        "(1) simulation çš„æŠ¥å‘Š markdownï¼ˆåŒ…å«æ¨¡æ‹ŸæŽ¨æ¼”çš„è¯æ®ä¸Žç»“è®ºï¼‰"
        "(2) interview evidenceï¼ˆå¦‚æžœæä¾›ï¼Œæ¥è‡ªçœŸå®žé‡‡è®¿/æ¨¡æ‹Ÿagentè§‚ç‚¹ï¼›å¯èƒ½ä¸ºç©ºï¼‰"
        "ç„¶åŽæŠŠè¯æ®ä¸Žæ¯ä¸ªå€™é€‰è§†é¢‘çš„ why_ranked/teaching_score/æ ‡é¢˜å†…å®¹è¿›è¡ŒåŒ¹é…ã€‚"
        "æœ€ç»ˆåªèƒ½é€‰æ‹©ä¸€ä¸ª best_indexï¼Œå¿…é¡»æ˜¯0..2ã€‚"
    )

    resp = llm.chat_json(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": str(user_payload)},
        ],
        temperature=0.2,
        max_tokens=500,
    )

    best_index = int(resp.get("best_index", 0))
    best_index = max(0, min(best_index, len(candidates) - 1))

    return {
        "best_index": best_index,
        "best_video": candidates[best_index],
        "reason": resp.get("reason"),
        "raw_llm": resp,
    }


@youtube_mirror_fish_bp.route("/best", methods=["POST"])
def mirror_fish_best():
    try:
        data = request.get_json() or {}
        topic = (data.get("topic") or "").strip()
        section_title = (data.get("section_title") or "").strip()
        simulation_id = (data.get("simulation_id") or "").strip()
        student_level = (data.get("student_level") or data.get("level") or "").strip()
        learning_goal = (data.get("learning_goal") or data.get("goal") or "").strip()
        course_context = (data.get("course_context") or data.get("context") or "").strip()

        if not topic:
            return jsonify({"success": False, "error": "è¯·æä¾› topic"}), 400
        if not simulation_id:
            return jsonify({"success": False, "error": "è¯·æä¾› simulation_id"}), 400

        youtube_helper = _load_youtube_helper()

        candidates = youtube_helper.get_videos_for_section(
            topic=topic,
            section_title=section_title,
            max_results=3,
            student_level=student_level,
            learning_goal=learning_goal,
            course_context=course_context,
        )
        if not candidates:
            return jsonify({"success": False, "error": "æœªæ‰¾åˆ°å€™é€‰è§†é¢‘"}), 404

        report = _get_report_markdown(simulation_id)
        if not report:
            return jsonify({
                "success": False,
                "error": f"æœªæ‰¾åˆ° simulation_id={simulation_id} çš„ reportï¼Œè¯·å…ˆç”ŸæˆæŠ¥å‘Š /api/report/generate"
            }), 404

        interview_evidence = _get_interview_evidence(simulation_id)

        chosen = _choose_best_by_llm(
            topic=topic,
            section_title=section_title,
            simulation_id=simulation_id,
            candidates=candidates[:3],
            report=report,
            interview_evidence=interview_evidence,
        )

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "topic": topic,
                "section_title": section_title,
                "student_level": student_level,
                "learning_goal": learning_goal,
                "candidates": candidates[:3],
                "best_video": chosen["best_video"],
                "best_index": chosen["best_index"],
                "reason": chosen.get("reason"),
                "evaluation": chosen.get("raw_llm"),
                "evidence": {
                    "report_id": report.get("report_id"),
                    "has_interview_evidence": interview_evidence is not None,
                }
            }
        })

    except Exception as e:
        logger.error(f"mirror-fish-best å¤±è´¥: {e}")
        return jsonify({"success": False, "error": str(e), "traceback": traceback.format_exc()}), 500


