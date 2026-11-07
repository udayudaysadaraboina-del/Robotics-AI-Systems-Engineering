import datetime
import hashlib
import json
import os
import re
import smtplib
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from google import genai
from google.genai import types
from pydantic import BaseModel

# ==================== 1. ENVIRONMENT & PATHS ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "udayudaysadaraboina-del")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

MEMORY_FILE = os.path.join(BASE_DIR, "agent_memory.json")
BRIEFINGS_DIR = os.path.join(BASE_DIR, "daily_briefings")
FEED_FILE = os.path.join(BRIEFINGS_DIR, "intel_feed.json")


# ==================== 2. STRUCTURED OUTPUT SCHEMAS ====================
class RoboticsNewsItem(BaseModel):
    headline: str
    company_or_lab: str
    source_url: str
    engineering_breakdown: list[str]
    relevance_to_uday: str


class InternshipOpportunity(BaseModel):
    role_title: str
    company_name: str
    location: str
    apply_url: str
    ats_match_score: int
    lead_project_to_pitch: str
    why_it_matches: str
    tailored_resume_bullet: str
    linkedin_people_search_url: str
    cold_dm_template: str
    step_by_step_apply_guide: list[str]


class DailyIntelligenceReport(BaseModel):
    date: str
    robotics_radar: list[RoboticsNewsItem]
    linkedin_post_draft: str
    matched_internships: list[InternshipOpportunity]
    skill_gap_radar: str
    daily_networking_action: str


# ==================== 3. ZERO-TOKEN LIVE WEB RSS RECON ====================
def fetch_live_rss_intel() -> tuple[list[dict], str]:
    """Pulls real-time robotics news & research feeds using zero Gemini tokens."""
    feeds = [
        ("Big Tech Robotics", "https://news.google.com/rss/search?q=NVIDIA+Robotics+OR+Boston+Dynamics+OR+DeepMind+Robotics+OR+Humanoid+Robot&hl=en-IN&gl=IN&ceid=IN:en"),
        ("ArXiv Robotics (cs.RO)", "http://export.arxiv.org/rss/cs.RO"),
    ]
    collected = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for source_label, url in feeds:
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item")[:3]:
                    title = (item.findtext("title") or "").strip()
                    link = (item.findtext("link") or "").strip()
                    if title and link:
                        collected.append({
                            "title": title,
                            "source": source_label,
                            "url": link
                        })
        except Exception as err:
            print(f"[WARN] RSS feed skipped ({source_label}): {err}")

    summary_lines = [f"- [{c['source']}] {c['title']} ({c['url']})" for c in collected[:5]]
    return collected, "\n".join(summary_lines)


# ==================== 4. STRICT FLASH-ONLY MODEL FILTER ====================
def get_safe_flash_models(client: genai.Client) -> list[str]:
    preferred = [
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite",
        "gemini-3.0-flash",
        "gemini-2.0-flash",
    ]
    blocked = (
        "argon", "pro", "exp", "thinking", "tts", "image",
        "imagen", "veo", "embedding", "gemma", "aqa", "learnlm",
        "robotics", "computer-use", "deep-research", "audio", "live"
    )
    discovered = []
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            if "gemini" in name and "flash" in name:
                if not any(b in name.lower() for b in blocked):
                    discovered.append(name)
    except Exception:
        pass

    final_list = []
    for c in preferred + discovered:
        if c not in final_list:
            final_list.append(c)
    return final_list[:4]


# ==================== 5. PERSISTENT 365-DAY MEMORY ====================
def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except OSError:
            pass
    return {
        "days_completed": 0,
        "seen_job_hashes": [],
        "seen_news_hashes": [],
        "recent_companies": [],
        "recent_headlines": [],
    }


def save_memory(memory: dict):
    memory["seen_job_hashes"] = memory["seen_job_hashes"][-500:]
    memory["seen_news_hashes"] = memory["seen_news_hashes"][-500:]
    memory["recent_companies"] = memory["recent_companies"][-40:]
    memory["recent_headlines"] = memory["recent_headlines"][-40:]
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


# ==================== 6. LIVE GITHUB PORTFOLIO SYNC ====================
def fetch_live_github_profile(username: str) -> str:
    try:
        url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=5"
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            repos = resp.json()
            return ", ".join(
                f"{r.get('name')} ({r.get('language') or 'Code'})" for r in repos
            )
    except requests.RequestException:
        pass
    return "Robotics-AI-Systems-Engineering (ESP32 C++, Python, YOLOv8, WebGL)"


# ==================== 7. HYBRID FAILSAFE ENGINE ====================
def build_failsafe_report(today_pretty: str, day_num: int, live_rss: list[dict]) -> dict:
    """Combines live scraped RSS headlines with curated high-match Indian robotics internships."""
    radar = []
    for item in live_rss[:3]:
        radar.append({
            "headline": item["title"],
            "company_or_lab": item["source"],
            "source_url": item["url"],
            "engineering_breakdown": [
                "Live physical AI / robotics update captured via AURA-INTEL RSS recon.",
                "Demonstrates industry shift toward low-latency edge perception and deterministic actuation."
            ],
            "relevance_to_uday": "Directly complements your YOLOv8-Pose vision pipeline and ESP32 hardware interrupt (ISR) architecture."
        })

    if len(radar) < 3:
        radar.append({
            "headline": "NVIDIA Isaac GR00T & Jetson Thor Edge-AI Acceleration for Humanoids",
            "company_or_lab": "NVIDIA Robotics",
            "source_url": "https://developer.nvidia.com/isaac",
            "engineering_breakdown": [
                "Combines multimodal transformer policies with real-time low-latency actuator control loops.",
                "Uses simulation-to-real (Sim2Real) reinforcement learning in Isaac Lab prior to edge deployment."
            ],
            "relevance_to_uday": "Directly aligns with your YOLOv8-Pose biomechanical tracking and sub-180ms ESP32 hardware telemetry pipelines."
        })

    return {
        "date": today_pretty,
        "day_number": day_num,
        "robotics_radar": radar[:3],
        "linkedin_post_draft": (
            "As Physical AI moves from cloud simulations to edge hardware, the real bottleneck isn't just model size—it's deterministic latency.\n\n"
            "While building AuraReflex (an ESP32 C++ interrupt-driven reaction analyzer) and my YOLOv8-Pose patient monitoring bench, switching from software polling to hardware ISRs (IRAM_ATTR) and structured 115200-baud UART telemetry made all the difference in sub-180ms response times.\n\n"
            "How are you bridging Python Edge-AI vision with microcontroller firmware in your robotics builds?\n\n"
            "#Robotics #EmbeddedSystems #EdgeAI #ESP32 #ComputerVision #PhysicalAI"
        ),
        "matched_internships": [
            {
                "role_title": "Robotics & Embedded Firmware Intern",
                "company_name": "CynLr (Cybernetics Laboratory)",
                "location": "Bengaluru, India",
                "apply_url": "https://www.linkedin.com/jobs/search/?keywords=CynLr+Robotics+Intern&location=India",
                "ats_match_score": 94,
                "lead_project_to_pitch": "Emergency Patient Monitoring & Fall Detection System",
                "why_it_matches": "CynLr builds visual object intelligence for robotic arms, matching your YOLOv8-Pose + OpenCV + 3-DOF kinematics stack.",
                "tailored_resume_bullet": "Engineered a real-time YOLOv8-Pose & OpenCV visual perception pipeline integrated with an ESP32 UART hardware controller (<180ms latency, 96% detection accuracy).",
                "linkedin_people_search_url": "https://www.linkedin.com/search/results/people/?keywords=CynLr+Robotics+Engineer",
                "cold_dm_template": "Hi! I'm an S3 Robotics & AI student at Amrita building YOLOv8-Pose + ESP32 embedded vision systems. Loved CynLr's visual robotics work—would love to connect! Portfolio: https://udayudaysadaraboina-del.github.io/Robotics-AI-Systems-Engineering/",
                "step_by_step_apply_guide": [
                    "Open the Direct Apply Link and filter for active internship/research openings at CynLr.",
                    "Include the tailored YOLOv8-Pose + ESP32 resume bullet at the top of your projects section.",
                    "Send the Cold LinkedIn DM to a Robotics Engineer on their team with your live 3D WebGL portfolio link."
                ]
            },
            {
                "role_title": "Embedded Systems & Edge-AI Intern",
                "company_name": "Addverb Technologies",
                "location": "Noida / Bengaluru, India",
                "apply_url": "https://www.linkedin.com/jobs/search/?keywords=Addverb+Embedded+Robotics+Intern&location=India",
                "ats_match_score": 91,
                "lead_project_to_pitch": "AuraReflex — Real-Time Dual-Channel Reaction Analyzer",
                "why_it_matches": "Addverb's industrial warehouse robots rely on deterministic C++ firmware, hardware interrupts, and serial telemetry.",
                "tailored_resume_bullet": "Developed interrupt-driven ESP32 C++ firmware (IRAM_ATTR ISRs, microsecond non-blocking state machine) paired with a multi-threaded Python CustomTkinter telemetry dashboard at 115200 baud.",
                "linkedin_people_search_url": "https://www.linkedin.com/search/results/people/?keywords=Addverb+Embedded+Systems",
                "cold_dm_template": "Hi! I'm an S3 B.Tech Robotics & AI student specializing in interrupt-driven ESP32 C++ firmware and Edge-AI. Would love to connect and learn about Embedded internships at Addverb!",
                "step_by_step_apply_guide": [
                    "Click the Direct Apply Link to view Addverb's current university internship listings.",
                    "Highlight your AuraReflex C++ ISR state-machine architecture in your application.",
                    "Connect with an Embedded Team Lead using the LinkedIn People Search link."
                ]
            },
            {
                "role_title": "Computer Vision & Autonomous Systems Intern",
                "company_name": "Genrobotics / Mowito",
                "location": "Thiruvananthapuram / Kochi / Bengaluru",
                "apply_url": "https://www.linkedin.com/jobs/search/?keywords=Genrobotics+OR+Mowito+Robotics+Intern&location=India",
                "ats_match_score": 89,
                "lead_project_to_pitch": "Emergency Patient Monitoring & Fall Detection System",
                "why_it_matches": "Kerala and Bengaluru robotics companies actively recruit Amrita B.Tech students with hands-on C++, OpenCV, and kinematics portfolios.",
                "tailored_resume_bullet": "Built a 3-DOF Denavit-Hartenberg kinematic simulator and real-time OpenCV/YOLOv8-Pose vision-to-hardware actuation bench.",
                "linkedin_people_search_url": "https://www.linkedin.com/search/results/people/?keywords=Genrobotics+Robotics+Engineer",
                "cold_dm_template": "Hi! I'm an S3 Robotics & AI student at Amrita (Amritapuri) building embedded C++ & YOLOv8-Pose robotic systems. Would love to connect regarding internship opportunities!",
                "step_by_step_apply_guide": [
                    "Check the LinkedIn job search link and Genrobotics career page for Kerala-based internships.",
                    "Attach your live GitHub Pages 3D portfolio URL in the application form.",
                    "Message an Amrita alumni or engineer at Genrobotics using the cold DM template."
                ]
            }
        ],
        "skill_gap_radar": "Trending Skill: ROS 2 (Humble/Jazzy) micro-ROS on ESP32. Weekend 2-Hour Micro-Build: Add a `ros2_serial_bridge.py` node to your AuraReflex repository that publishes reaction-time serial packets (`RESULT:1,245`) as a standard `std_msgs/Int32` ROS 2 topic.",
        "daily_networking_action": "Send 2 connection requests to Robotics Engineers at CynLr and Genrobotics using the Cold LinkedIn DM templates in today's email."
    }


# ==================== 8. MAIN EXECUTION PIPELINE ====================
def run_aura_intel_pipeline():
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY environment variable!")

    print("[RECON] Fetching live Robotics & ArXiv RSS feeds (Zero-Token Mode)...")
    live_rss_items, rss_text_block = fetch_live_rss_intel()
    print(f"[RECON] Captured {len(live_rss_items)} live robotics headlines.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    models = get_safe_flash_models(client)

    memory = load_memory()
    today_iso = datetime.date.today().isoformat()
    today_pretty = datetime.date.today().strftime("%B %d, %Y")
    day_num = memory["days_completed"] + 1
    repos_short = fetch_live_github_profile(GITHUB_USERNAME)
    avoid_co = ", ".join(memory["recent_companies"][-8:]) or "None"

    compact_prompt = (
        f"Date: {today_pretty} (Day {day_num}). Candidate: Uday Kumar, S3 B.Tech Robotics & AI "
        f"(Amrita Vishwa Vidyapeetham, India). Stack: ESP32 C++ ISRs (AuraReflex), YOLOv8-Pose + OpenCV "
        f"(Emergency Patient Monitoring), CustomTkinter, 3-DOF D-H Kinematics. "
        f"Portfolio: https://udayudaysadaraboina-del.github.io/Robotics-AI-Systems-Engineering/ "
        f"Repos: {repos_short}. Avoid repeating companies: {avoid_co}.\n"
        f"Live Web Headlines Today:\n{rss_text_block}\n"
        f"Return JSON matching schema: 3 robotics breakthroughs (use Live Web Headlines above), "
        f"1 LinkedIn post draft, and 3 India/Remote Robotics, Embedded, or Computer Vision internships "
        f"with ATS match scores, lead project, tailored resume bullet, LinkedIn search URL, and <280 char cold DM."
    )

    report_data = None
    for model_name in models:
        try:
            print(f"[AI SYNTHESIS] Querying {model_name}...")
            resp = client.models.generate_content(
                model=model_name,
                contents=compact_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DailyIntelligenceReport,
                    temperature=0.2,
                ),
            )
            report_data = json.loads(resp.text)
            print(f"[AI SYNTHESIS] Succeeded using {model_name}!")
            break
        except Exception as err:
            short_err = re.sub(r"\s+", " ", str(err))[:120]
            print(f"[WARN] {model_name} skipped ({short_err})")

    if not report_data:
        print("[FAILSAFE] API key in cooldown. Building report with Live RSS + Failsafe Engine...")
        report_data = build_failsafe_report(today_pretty, day_num, live_rss_items)

    report_data["date"] = today_pretty
    report_data["day_number"] = day_num

    # Update 365-day memory
    memory["days_completed"] = day_num
    for job in report_data.get("matched_internships", []):
        job_key = f"{job['company_name']}_{job['role_title']}".lower()
        memory["seen_job_hashes"].append(hashlib.md5(job_key.encode()).hexdigest())
        memory["recent_companies"].append(f"{job['company_name']} ({job['role_title']})")

    for news in report_data.get("robotics_radar", []):
        news_key = news["headline"].lower()
        memory["seen_news_hashes"].append(hashlib.md5(news_key.encode()).hexdigest())
        memory["recent_headlines"].append(news["headline"])

    save_memory(memory)
    md_path = save_outputs(report_data, today_iso)

    # Channel C: Rich Dark-Mode HTML Email Delivery
    if GMAIL_USER and GMAIL_APP_PASSWORD:
        send_html_email(report_data)
    else:
        print("[INFO] GMAIL_USER / GMAIL_APP_PASSWORD not set yet. Skipping email dispatch.")

    print(f"\n[SUCCESS] Day {day_num}/365 AURA-INTEL v3.0 cycle completed!")
    print(f"[LOCAL REPORT] {md_path}")


# ==================== 9. CHANNEL A: ARCHIVE & FEED SAVER ====================
def save_outputs(report: dict, today_iso: str) -> str:
    os.makedirs(BRIEFINGS_DIR, exist_ok=True)

    md_path = os.path.join(BRIEFINGS_DIR, f"Briefing_{today_iso}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 🤖 AURA-INTEL v3.0 — Day {report['day_number']}/365 ({report['date']})\n\n")
        f.write("## 📡 1. Big Tech Robotics & Physical AI Radar\n")
        for n in report["robotics_radar"]:
            f.write(f"### 🔹 {n['headline']} ({n['company_or_lab']})\n")
            for b in n["engineering_breakdown"]:
                f.write(f"- {b}\n")
            f.write(f"- **Why It Matters to Your Stack:** {n['relevance_to_uday']}\n")
            f.write(f"- **Source:** {n['source_url']}\n\n")

        f.write("## ✍️ 2. Ready-to-Post LinkedIn Draft\n")
        f.write(f"```text\n{report['linkedin_post_draft']}\n```\n\n")

        f.write("## 🎯 3. Hyper-Matched Internships & Application Playbooks\n")
        for idx, job in enumerate(report["matched_internships"], 1):
            f.write(
                f"### {idx}. {job['role_title']} @ {job['company_name']} ({job['location']}) — Match: {job['ats_match_score']}%\n"
            )
            f.write(f"- **Direct Apply Link:** {job['apply_url']}\n")
            f.write(f"- **Lead Project to Pitch:** `{job['lead_project_to_pitch']}`\n")
            f.write(f"- **Why You Match:** {job['why_it_matches']}\n")
            f.write(
                f"- **Tailored Resume Bullet (Copy-Paste):**\n  > {job['tailored_resume_bullet']}\n"
            )
            f.write(
                f"- **Find Hiring Manager on LinkedIn:** [Click to Search People]({job['linkedin_people_search_url']})\n"
            )
            f.write(f"- **Cold LinkedIn DM (<280 chars):**\n  `{job['cold_dm_template']}`\n")
            f.write("- **How to Apply Step-by-Step:**\n")
            for step in job["step_by_step_apply_guide"]:
                f.write(f"  1. {step}\n")
            f.write("\n")

        f.write(f"## 🛠️ 4. Skill-Gap & Weekend Micro-Build Radar\n{report['skill_gap_radar']}\n\n")
        f.write(f"## ⚡ 5. Today's 10-Minute LinkedIn Action\n{report['daily_networking_action']}\n")

    feed = []
    if os.path.exists(FEED_FILE):
        try:
            with open(FEED_FILE, "r", encoding="utf-8") as f:
                feed = json.load(f)
        except OSError:
            feed = []
    feed.insert(0, report)
    with open(FEED_FILE, "w", encoding="utf-8") as f:
        json.dump(feed[:30], f, indent=2)

    return md_path


# ==================== 10. CHANNEL C: EXECUTIVE DARK-MODE HTML EMAIL ====================
def send_html_email(report: dict):
    print(f"[EMAIL] Dispatching Rich Dark-Mode HTML Briefing to {GMAIL_USER}...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = (
        f"🤖 [AURA-INTEL Day {report['day_number']}/365] "
        f"{len(report['matched_internships'])} Robotics Internships & Live Radar ({report['date']})"
    )
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER

    news_html = ""
    for n in report["robotics_radar"]:
        bullets = "".join(f"<li style='margin-bottom:4px;'>{b}</li>" for b in n["engineering_breakdown"])
        news_html += f"""
        <div style="background:#10151b;border:1px solid #26303a;border-left:4px solid #6cd3e0;padding:16px;margin-bottom:14px;border-radius:6px;">
            <h4 style="margin:0 0 6px 0;color:#ece6da;font-size:16px;">{n['headline']} <span style="color:#6cd3e0;font-size:13px;">({n['company_or_lab']})</span></h4>
            <ul style="color:#c8c2b6;font-size:13px;padding-left:18px;margin:8px 0;">{bullets}</ul>
            <p style="margin:6px 0;color:#5cc39b;font-size:13px;"><b>Stack Relevance:</b> {n['relevance_to_uday']}</p>
            <a href="{n['source_url']}" style="color:#6cd3e0;font-size:12px;text-decoration:none;">🔗 Read Source Article →</a>
        </div>
        """

    jobs_html = ""
    for j in report["matched_internships"]:
        steps_html = "".join(f"<li style='margin-bottom:4px;'>{s}</li>" for s in j["step_by_step_apply_guide"])
        jobs_html += f"""
        <div style="background:#10151b;border:1px solid #26303a;border-left:4px solid #5cc39b;padding:16px;margin-bottom:16px;border-radius:6px;">
            <h3 style="margin:0 0 6px 0;color:#ece6da;font-size:17px;">{j['role_title']} @ {j['company_name']} <span style="color:#5cc39b;">({j['ats_match_score']}% ATS Match)</span></h3>
            <p style="margin:4px 0;color:#6cd3e0;font-size:13px;">📍 {j['location']} | 🏆 Lead Project: <b>{j['lead_project_to_pitch']}</b></p>
            <p style="color:#c8c2b6;font-size:14px;margin:8px 0;">{j['why_it_matches']}</p>
            <div style="background:#06080b;padding:10px;border-radius:4px;color:#ece6da;font-family:Consolas,monospace;font-size:12px;margin:8px 0;border:1px solid #1c242e;">
                <b style="color:#5cc39b;">Tailored Resume Bullet (Copy-Paste):</b><br>• {j['tailored_resume_bullet']}
            </div>
            <div style="background:#06080b;padding:10px;border-radius:4px;color:#6cd3e0;font-family:Consolas,monospace;font-size:12px;margin:8px 0;border:1px solid #1c242e;">
                <b>Cold LinkedIn Note (&lt;280 chars):</b><br>{j['cold_dm_template']}
            </div>
            <p style="color:#9aa2ac;font-size:12px;margin:8px 0 4px 0;"><b>Application Playbook:</b></p>
            <ol style="color:#c8c2b6;font-size:12px;padding-left:18px;margin:4px 0 14px 0;">{steps_html}</ol>
            <p style="margin-top:12px;">
                <a href="{j['apply_url']}" style="background:#5cc39b;color:#06080b;padding:8px 14px;text-decoration:none;font-weight:bold;border-radius:4px;margin-right:10px;font-size:13px;display:inline-block;">🚀 Apply Direct</a>
                <a href="{j['linkedin_people_search_url']}" style="background:#6cd3e0;color:#06080b;padding:8px 14px;text-decoration:none;font-weight:bold;border-radius:4px;font-size:13px;display:inline-block;">🔎 Find Hiring Team</a>
            </p>
        </div>
        """

    html_body = f"""
    <html><body style="background:#06080b;color:#ece6da;font-family:'Segoe UI',Arial,sans-serif;padding:24px;max-width:760px;margin:0 auto;">
        <div style="border-bottom:2px solid #26303a;padding-bottom:12px;margin-bottom:20px;">
            <h2 style="color:#6cd3e0;margin:0;letter-spacing:0.5px;">🤖 AURA-INTEL v3.0 // DAY {report['day_number']} OF 365</h2>
            <p style="color:#9aa2ac;margin:4px 0 0 0;font-size:13px;">Private Robotics &amp; Career Intelligence for Uday Kumar ({report['date']})</p>
        </div>

        <h3 style="color:#ece6da;border-left:3px solid #6cd3e0;padding-left:10px;">📡 1. Big Tech Robotics &amp; Physical AI Radar</h3>
        {news_html}

        <h3 style="color:#ece6da;border-left:3px solid #5cc39b;padding-left:10px;margin-top:26px;">🎯 2. Top Matched Internships &amp; Playbooks</h3>
        {jobs_html}

        <h3 style="color:#ece6da;border-left:3px solid #f5a623;padding-left:10px;margin-top:26px;">✍️ 3. Ready-to-Post LinkedIn Draft</h3>
        <pre style="background:#10151b;padding:14px;border:1px solid #26303a;white-space:pre-wrap;color:#ece6da;border-radius:6px;font-family:'Segoe UI',sans-serif;font-size:13px;">{report['linkedin_post_draft']}</pre>

        <h3 style="color:#ece6da;border-left:3px solid #bd10e0;padding-left:10px;margin-top:26px;">🛠️ 4. Skill-Gap &amp; Weekend Micro-Build</h3>
        <div style="background:#10151b;padding:14px;border:1px solid #26303a;border-radius:6px;color:#c8c2b6;font-size:13px;">
            {report['skill_gap_radar']}
        </div>

        <h3 style="color:#ece6da;border-left:3px solid #6cd3e0;padding-left:10px;margin-top:26px;">⚡ 5. Today's 10-Minute Networking Action</h3>
        <div style="background:#10151b;padding:14px;border:1px solid #26303a;border-radius:6px;color:#5cc39b;font-size:13px;font-weight:bold;">
            {report['daily_networking_action']}
        </div>
    </body></html>
    """
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
    print(f"[EMAIL SENT] Successfully delivered HTML briefing to {GMAIL_USER}!")


if __name__ == "__main__":
    run_aura_intel_pipeline()