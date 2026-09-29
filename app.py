from io import BytesIO
import os
from pathlib import Path

import streamlit as st

from src.gemini_agent import GeminiServiceError, analyze_plan_image, draw_candidate_overlay, explain_findings, test_gemini_connection
from src.annotations import annotate_plan, annotate_compliance_overlay
from src.checks import run_checks, summarize
from src.models import ProjectInput, Status
from src.plan_reader import find_dimension_candidates, render_plan
from src.report import create_report
from src.rules import load_rule_pack


ROOT = Path(__file__).parent
RULE_FILES = {
    "5_marla_residential": ROOT / "data/rules/lda_5_marla_residential.yaml",
    "10_marla_residential": ROOT / "data/rules/lda_10_marla_residential.yaml",
}
PLOT_CLASS_LABELS = {
    "5_marla_residential": "5 Marla Residential",
    "10_marla_residential": "10 Marla Residential",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ADVISORY = "NaqshaCheck provides an advisory pre-submission review. It does not issue official approval, replace a licensed architect or guarantee acceptance by any authority."
AI_FIELDS = {
    "road_width_ft": ("Road width (ft)", "road_width"),
    "plot_width_ft": ("Plot width (ft)", "plot_width"),
    "plot_depth_ft": ("Plot depth (ft)", "plot_depth"),
    "front_setback_ft": ("Front setback (ft)", "front"),
    "rear_setback_ft": ("Rear setback (ft)", "rear"),
    "left_setback_ft": ("Left setback (ft)", "side_l"),
    "right_setback_ft": ("Right setback (ft)", "side_r"),
    "covered_area_sqft": ("Ground-floor covered area (sq ft)", "covered_area"),
    "building_height_ft": ("Building height (ft)", "height"),
    "stair_width_ft": ("Clear stair width (ft)", "stair_width"),
    "parking_spaces": ("Parking spaces", "parking"),
}



def get_gemini_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key
    try:
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


st.set_page_config(page_title="NaqshaCheck", page_icon="📐", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
:root { --navy:#0b2239; --navy2:#102f4d; --ink:#10233e; --muted:#63738a; --line:#e3e9ef; --green:#079455; --amber:#f59e0b; --red:#ef4444; }
.stApp { background:#fff; color:var(--ink); }
.block-container { padding:1.45rem 2rem 2rem; max-width:1500px; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0b2239 0%,#102f4d 100%); border-right:1px solid #24445f; }
[data-testid="stSidebar"] > div:first-child { padding-top:0.5rem; }
[data-testid="stSidebar"] * { color:#f8fbff; }
[data-testid="stSidebar"] [data-testid="stAlert"] { background:rgba(255,255,255,.08); border-color:rgba(255,255,255,.13); }
[data-testid="stHeader"] { background:#0b2239; }
h1,h2,h3 { color:var(--ink); letter-spacing:-.025em; }
h1 { font-size:1.55rem!important; margin-bottom:.1rem!important; }
h2 { font-size:1.25rem!important; }
h3 { font-size:1.05rem!important; }
p, label, .stCaption { color:var(--muted); }
.nc-brand { font-size:1.6rem; font-weight:800; margin:.2rem 0 .15rem; }
.nc-brand-sub { color:#b8c8d8!important; margin-bottom:1.8rem; }
.nc-step { display:flex; gap:.8rem; padding:.8rem .25rem; align-items:flex-start; }
.nc-step-num { width:2rem;height:2rem;min-width:2rem;border-radius:50%;background:#6e87a0;color:white;display:flex;align-items:center;justify-content:center;font-weight:700; }
.nc-step.active .nc-step-num { background:#3b82f6; box-shadow:0 0 0 4px rgba(59,130,246,.15); }
.nc-step-title { font-weight:700; color:white; line-height:1.2; }
.nc-step-sub { font-size:.82rem; color:#aebed0; margin-top:.25rem; }
.nc-topbar { margin:-1.45rem -2rem 1.2rem; padding:.82rem 2rem; background:#0b2239; color:white; border-bottom:1px solid #23405b; display:flex; align-items:center; gap:1.3rem; }
.nc-topbar strong { font-size:1.15rem; }.nc-topbar span { color:#c8d5e2; border-left:1px solid #29445d; padding-left:1.3rem; }
.nc-panel { border:1px solid var(--line); border-radius:10px; padding:1rem 1.1rem; background:#fff; box-shadow:0 1px 2px rgba(16,35,62,.03); }
.nc-note { border:1px solid #dbe5ee; border-left:4px solid #3b82f6; padding:.65rem .85rem; border-radius:7px; background:#f7fafc; color:#46566a; font-size:.86rem; }
.nc-wait { border:1px dashed #cdd8e3; background:#f8fafc; border-radius:9px; padding:1rem; color:#66778c; text-align:center; }
.nc-rulebar { font-size:.78rem; color:#718096; margin:.2rem 0 .9rem; }
[data-testid="stFileUploader"] { border:1px solid var(--line); border-radius:9px; padding:.45rem; background:#f8fafc; }
[data-testid="stMetric"] { border:1px solid var(--line); border-radius:9px; padding:.8rem 1rem; background:white; min-height:110px; }
[data-testid="stMetricLabel"] p { font-weight:700; }
[data-testid="stMetricValue"] { font-weight:800; }
.stButton > button[kind="primary"] { background:#079455; border-color:#079455; border-radius:7px; font-weight:700; min-height:3rem; }
.stButton > button[kind="primary"]:hover { background:#067647; border-color:#067647; }
.stButton > button:not([kind="primary"]) { border-radius:7px; }
[data-baseweb="tab-list"] { gap:.35rem; border-bottom:1px solid var(--line); }
button[data-baseweb="tab"] { font-weight:700; padding:.65rem 1rem; }
[data-testid="stExpander"] { border:1px solid var(--line); border-radius:8px; }
hr { border-color:rgba(255,255,255,.12)!important; }
@media (max-width: 900px) { .block-container{padding:1rem}.nc-topbar{margin:-1rem -1rem 1rem;padding:.8rem 1rem;} }
</style>
""", unsafe_allow_html=True)

selected_plot_class = st.session_state.get("plot_class_select", "5_marla_residential")
if selected_plot_class not in RULE_FILES:
    selected_plot_class = "5_marla_residential"
metadata, rules = load_rule_pack(RULE_FILES[selected_plot_class])
gemini_key = get_gemini_key()

with st.sidebar:
    st.markdown('<div class="nc-brand">NaqshaCheck</div><div class="nc-brand-sub">Pre-submission review</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="nc-step active"><div class="nc-step-num">1</div><div><div class="nc-step-title">Project</div><div class="nc-step-sub">Basic information</div></div></div>
    <div class="nc-step"><div class="nc-step-num">2</div><div><div class="nc-step-title">Upload</div><div class="nc-step-sub">Plans and documents</div></div></div>
    <div class="nc-step"><div class="nc-step-num">3</div><div><div class="nc-step-title">Measurements</div><div class="nc-step-sub">Verify key dimensions</div></div></div>
    <div class="nc-step"><div class="nc-step-num">4</div><div><div class="nc-step-title">Review</div><div class="nc-step-sub">Compliance results</div></div></div>
    """, unsafe_allow_html=True)
    st.divider()
    st.caption(f"{metadata['authority']} · {metadata['plot_class']} · Rule version {metadata['version']}")
    if gemini_key:
        st.success("Gemini vision ready")
        with st.expander("Gemini connection diagnostic"):
            st.caption("Tests Gemini separately from plan analysis. Your API key is never displayed.")
            if st.button("Test Gemini connection", key="test_gemini_connection"):
                with st.spinner("Testing Gemini…"):
                    st.session_state.gemini_diagnostic = test_gemini_connection(api_key=gemini_key)
            diag = st.session_state.get("gemini_diagnostic")
            if diag:
                st.write("✓ Secret detected" if diag["secret_detected"] else "✗ Secret not detected")
                st.write("✓ SDK available" if diag["sdk_available"] else "✗ google-genai not installed")
                st.write("✓ Gemini request succeeded" if diag["authenticated"] else "✗ Gemini request failed")
                st.caption(diag["message"])
    else:
        st.info("Plan AI off · add GEMINI_API_KEY in Streamlit Secrets")


st.markdown('<div class="nc-topbar"><strong>NaqshaCheck</strong><span>Pre-submission review</span></div>', unsafe_allow_html=True)
st.title("Building plan preflight")
st.caption("Review project information, verify plan measurements and run selected preflight checks before authority submission.")
st.markdown(f'<div class="nc-note"><b>Advisory pre-submission review.</b> {ADVISORY}</div>', unsafe_allow_html=True)

project_tab, upload_tab, review_tab = st.tabs(["1  Project", "2  Upload & AI review", "3  Compliance review"])

with project_tab:
    st.subheader("Project details")
    st.caption("Provide key information about your project. Compliance uses human-confirmed values only; AI candidates are never inserted silently.")
    left, right = st.columns(2)
    with left:
        authority = st.selectbox("Authority *", ["LDA"], help="MVP currently supports professionally reviewed LDA residential rule packs.")
        plot_class = st.selectbox(
            "Plot class *",
            options=list(RULE_FILES),
            format_func=lambda value: PLOT_CLASS_LABELS[value],
            key="plot_class_select",
            help="Select the professionally reviewed rule pack that applies to the project.",
        )
        title = st.text_input("Project title (optional)", f"{PLOT_CLASS_LABELS[plot_class]} House")
        location = st.text_input("Location / Sector (optional)", "Lahore")
        road_width = st.number_input("Road width (ft) *", 1.0, 300.0, 30.0, 1.0, key="road_width")
        plot_width = st.number_input("Plot width (ft)", 1.0, 500.0, 25.0, 0.5, key="plot_width")
        plot_depth = st.number_input("Plot depth (ft)", 1.0, 1000.0, 45.0, 0.5, key="plot_depth")
    with right:
        front = st.number_input("Front setback (ft)", 0.0, 100.0, 5.0, 0.5, key="front")
        rear = st.number_input("Rear setback (ft)", 0.0, 100.0, 5.0, 0.5, key="rear")
        side_l = st.number_input("Left setback (ft)", 0.0, 100.0, 0.0, 0.5, key="side_l")
        side_r = st.number_input("Right setback (ft)", 0.0, 100.0, 0.0, 0.5, key="side_r")
        covered_area = st.number_input("Ground-floor covered area (sq ft)", 1.0, 100000.0, 800.0, 10.0, key="covered_area")
        height = st.number_input("Building height (ft)", 1.0, 500.0, 30.0, 0.5, key="height")
        stair_width = st.number_input("Clear stair width (ft)", 1.0, 20.0, 3.5, 0.25, key="stair_width")
        parking = st.number_input("Parking spaces", 0, 100, 1, 1, key="parking")
        st.caption("Parking is recorded as project information but is not treated as a mandatory numeric violation in these reviewed ordinary residential rule packs.")

    st.session_state.project = ProjectInput(
        authority=authority, plot_class=plot_class, project_title=title,
        location=location, road_width_ft=road_width, plot_width_ft=plot_width,
        plot_depth_ft=plot_depth, front_setback_ft=front, rear_setback_ft=rear,
        left_setback_ft=side_l, right_setback_ft=side_r, covered_area_sqft=covered_area,
        building_height_ft=height, stair_width_ft=stair_width, parking_spaces=parking,
    )
    st.info(f"Calculated plot area: **{st.session_state.project.plot_area_sqft:,.0f} sq ft** · Coverage: **{st.session_state.project.coverage_percent:.1f}%**")

with upload_tab:
    st.subheader("Architectural plan")
    st.caption("Upload your floor plan (PDF, JPG or PNG). Make sure labels and dimensions are clear and readable.")
    upload = st.file_uploader("Upload plan", type=["pdf", "png", "jpg", "jpeg"])
    if upload:
        file_bytes = upload.getvalue()
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            st.error("Upload exceeds the 25 MB MVP limit. Please reduce the file size before continuing.")
        else:
            try:
                image, extracted_text = render_plan(file_bytes, upload.name)
                st.session_state.plan_image = image
                st.image(image, caption=f"Preview: {upload.name}", use_container_width=True)
                candidates = find_dimension_candidates(extracted_text)
                if candidates:
                    st.write("Dimensions found in PDF text layer:", ", ".join(candidates))
                else:
                    st.caption("No reliable dimensions were found in the PDF text layer. Confirm measurements manually before checking.")

                if gemini_key:
                    if st.button("Analyze visible plan labels with Gemini", help="Advisory extraction only; no compliance decision is made."):
                        with st.spinner("Reading visible labels and dimensions…"):
                            try:
                                st.session_state.ai_plan_analysis = analyze_plan_image(image, api_key=gemini_key)
                            except GeminiServiceError as error:
                                st.error(str(error))
                    analysis = st.session_state.get("ai_plan_analysis")
                    if analysis:
                        st.subheader("AI measurement suggestions — confirmation required")
                        if analysis.model_used:
                            if analysis.fallback_used:
                                st.success(f"Plan analyzed with fallback model `{analysis.model_used}` because the primary model was temporarily unavailable.")
                            else:
                                st.caption(f"Gemini model used: `{analysis.model_used}`")
                        st.warning("These are extraction suggestions, not verified measurements or compliance findings. Confirm or correct each value before use.")
                        if any(obs.box_2d for obs in analysis.observations):
                            st.image(
                                draw_candidate_overlay(image, analysis),
                                caption="AI evidence locations (blue = unconfirmed Gemini extraction candidate)",
                                use_container_width=True,
                            )
                        confirmed: dict[str, float | int] = {}
                        for idx, obs in enumerate(analysis.observations):
                            label, _ = AI_FIELDS.get(obs.field, (obs.field, ""))
                            with st.container(border=True):
                                st.write(f"**{label}:** {obs.value} {obs.unit} · confidence **{obs.confidence:.0%}**")
                                st.caption(f"Evidence: {obs.evidence}")
                                if obs.field in AI_FIELDS and isinstance(obs.value, (int, float)):
                                    corrected = st.number_input(
                                        f"Confirm/correct {label}", value=float(obs.value), key=f"ai_value_{idx}"
                                    )
                                    if st.checkbox("I confirm this measurement candidate", key=f"ai_confirm_{idx}"):
                                        confirmed[obs.field] = int(corrected) if obs.field == "parking_spaces" else corrected
                        if analysis.uncertainties:
                            st.write("**Uncertainties / unreadable information**")
                            for uncertainty in analysis.uncertainties:
                                st.write(f"- {uncertainty}")
                        if st.button("Apply confirmed candidates to measurement form", disabled=not confirmed):
                            applied = {}
                            for field, value in confirmed.items():
                                mapping = AI_FIELDS.get(field)
                                if not mapping:
                                    continue
                                widget_key = mapping[1]
                                cast_value = int(value) if field == "parking_spaces" else float(value)
                                st.session_state[widget_key] = cast_value
                                applied[field] = cast_value
                            st.session_state.ai_confirmed_measurements = applied
                            # Existing findings are now stale because measurements changed.
                            st.session_state.pop("findings", None)
                            st.session_state.pop("ai_result_explanation", None)
                            st.session_state.apply_notice = f"Applied {len(applied)} confirmed measurement(s). Open the Project tab to review them, then run the compliance check."
                            st.rerun()

                        if st.session_state.get("apply_notice"):
                            st.success(st.session_state.apply_notice)
                else:
                    st.info("AI plan analysis is disabled until GEMINI_API_KEY is configured. Manual deterministic checking remains available.")
            except Exception as error:
                st.error(f"The file could not be read: {error}")
    else:
        st.info("Upload a clear plan. Text-based PDFs work best; uploaded plans are processed in memory and are not intentionally retained by this MVP.")

with review_tab:
    if "project" not in st.session_state:
        st.warning("Complete the project measurements first.")
    else:
        st.subheader("Compliance findings")
        st.caption(f"Based on {metadata['authority']} rules for {metadata['plot_class']}. Results appear only after deterministic checking.")
        if "findings" not in st.session_state:
            st.markdown('<div class="nc-wait"><b>Waiting for compliance check</b><br>Confirm the project measurements, then run the deterministic preflight check.</div>', unsafe_allow_html=True)
            st.write("")
        if st.button("▶  Run compliance check", type="primary", use_container_width=True):
            st.session_state.findings = run_checks(st.session_state.project, rules)
        if "findings" in st.session_state:
            findings = st.session_state.findings
            summary = summarize(findings)
            c1, c2, c3 = st.columns(3)
            c1.metric("Passed selected preflight checks", summary["pass"])
            c2.metric("Professional review required", summary["review"])
            c3.metric("Likely violations", summary["violation"])
            st.caption(f"Rule pack version: {metadata['version']} · Status: {metadata.get('source_status', metadata.get('status', 'unknown'))}")
            for item in findings:
                icon = "✅" if item.status == Status.PASS else "⚠️"
                status_label = "Passed selected preflight check" if item.status == Status.PASS else "Likely violation"
                with st.expander(f"{icon} {item.title} — {status_label}"):
                    st.write(f"**Measured:** {item.actual} {item.unit}")
                    st.write(f"**Required:** {item.required} {item.unit}")
                    st.write(item.message)
                    st.caption(f"Rule {item.rule_id} · Version {metadata['version']} · Citation: {item.citation}")

            if gemini_key:
                if st.button("Explain findings with Gemini", help="Explains deterministic results only; it cannot add or override rules."):
                    rules_by_id = {rule.id: rule for rule in rules}
                    finding_payload = []
                    for finding in findings:
                        rule = rules_by_id[finding.rule_id]
                        finding_payload.append({
                            "rule_id": finding.rule_id,
                            "title": finding.title,
                            "status": "Passed selected preflight check" if finding.status == Status.PASS else "Likely violation",
                            "actual": finding.actual,
                            "required_operator": rule.operator,
                            "required_value": rule.value,
                            "unit": finding.unit,
                            "citation": finding.citation,
                            "rule_version": metadata["version"],
                            "calculated_difference": round(float(finding.actual) - float(rule.value), 2),
                        })
                    try:
                        st.session_state.ai_result_explanation = explain_findings(
                            st.session_state.project.model_dump(),
                            finding_payload,
                            api_key=gemini_key,
                        )
                    except GeminiServiceError as error:
                        st.error(str(error))
                explanation = st.session_state.get("ai_result_explanation")
                if explanation:
                    st.subheader("Gemini explanation of deterministic findings")
                    if explanation.model_used:
                        if explanation.fallback_used:
                            st.success(f"Explanation generated with fallback model `{explanation.model_used}`.")
                        else:
                            st.caption(f"Gemini model used: `{explanation.model_used}`")
                    st.caption("Advisory explanation only. The deterministic findings above remain authoritative within this application.")
                    st.write(explanation.summary)
                    for item in explanation.items:
                        st.write(f"**{item.priority.title()} · {item.rule_id}:** {item.explanation}")
                        st.write(f"Correction guidance: {item.correction_guidance}")
                    st.caption(explanation.disclaimer)
            else:
                st.caption("Gemini explanation unavailable until GEMINI_API_KEY is configured.")

            report = create_report(st.session_state.project, findings, metadata["version"])
            st.download_button("Download PDF report", report, "naqshacheck-report.pdf", "application/pdf", use_container_width=True)
            if "plan_image" in st.session_state:
                analysis = st.session_state.get("ai_plan_analysis")
                confirmed_fields = set(st.session_state.get("ai_confirmed_measurements", {}).keys())
                if analysis and confirmed_fields:
                    annotated = annotate_compliance_overlay(
                        st.session_state.plan_image,
                        analysis,
                        findings,
                        rules,
                        confirmed_fields,
                    )
                    overlay_caption = "Compliance overlay: red = likely violation, green = passed selected check, blue = detected but not confirmed."
                else:
                    annotated = annotate_plan(st.session_state.plan_image, findings)
                    overlay_caption = "Annotated preflight preview. Confirm AI measurements to enable location-based compliance colors."
                buffer = BytesIO()
                annotated.save(buffer, format="PNG")
                st.image(annotated, caption=overlay_caption, use_container_width=True)
                st.download_button("Download annotated plan", buffer.getvalue(), "annotated-plan.png", "image/png", use_container_width=True)
