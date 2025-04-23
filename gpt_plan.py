#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib, re, datetime as dt
from openai import OpenAI
# -------- 基本路径 --------
GRAPH_DIR = "~/Documents/03Resources/Irisviel22"
JOURNALS  = pathlib.Path(GRAPH_DIR).expanduser() / "journals"
TASK_RE   = re.compile(r"^- (TODO|DONE)\s+(.*)$")
DUR_DONE = re.compile(r"\[耗时\s*([0-9\.]+)h\]")      # DONE 后标注实际耗时
DUR_TODO = re.compile(r"\[已耗时\s*([0-9\.]+)h\]")
EST_RE   = re.compile(r"\(预计\s*([0-9\.]+)h\)")       # TODO 内标注预计时长
MODEL     = "gpt-4o-mini"
client    = OpenAI()
# ---------------------------------------------

# ---------- 阶段定义 ----------
PHASES = [
    ("P0", dt.date(2025,4,22), dt.date(2025,5,15),
     "2D CFD: Stokes5 & focusing wave, grid convergence (<3%)"),
    ("P1", dt.date(2025,5,16), dt.date(2025,6,10),
     "2D NewWave focusing wave + draft"),
    ("P2", dt.date(2025,6,11), dt.date(2025,7,1),
     "2D wind-wave coupling, reflection (<2%)"),
    ("P3", dt.date(2025,7,2), dt.date(2025,7,20),
     "3D FOWT static blades ×2 moorings"),
    ("P4", dt.date(2025,7,21), dt.date(2025,8,1),
     "Thesis >=60 p + PPT 20 p"),
]
# ---------- 辅助函数 ----------
def get_current_phase(today=None):
    today = today or dt.date.today()
    for code,start,end,desc in PHASES:
        if start<=today<=end: return code,desc
    return PHASES[-1][0],PHASES[-1][3]

def get_time_progress(code):
    phase = {c:(s,e) for c,s,e,_ in PHASES}[code]
    start,end = phase
    today     = dt.date.today()
    if today<=start: return 0.0
    if today>=end:   return 1.0
    return (today-start).days/(end-start).days

def parse_tasks_for_date(date):
    done, todo = [], []
    file = JOURNALS / f"{date:%Y_%m_%d}.md"
    if not file.exists(): return done, todo

    for line in file.open(encoding="utf-8"):
        m = TASK_RE.match(line.strip())
        if not m: continue
        st, txt = m.groups()

        est = EST_RE.search(txt)
        est = float(est.group(1)) if est else 2.0    # 默认 2 h

        if st == "DONE":
            dur = DUR_DONE.search(txt)
            dur = float(dur.group(1)) if dur else est
            txt = DUR_DONE.sub("", EST_RE.sub("", txt)).strip()
            done.append({"text": txt, "est": est, "dur": dur})

        else:  # TODO
            spent = DUR_TODO.search(txt)
            spent = float(spent.group(1)) if spent else 0.0
            txt = DUR_TODO.sub("", EST_RE.sub("", txt)).strip()
            todo.append({"text": txt, "est": est, "spent": spent})
    return done, todo
    
# ---------- GPT 生成 ----------

def gpt_next_steps(prev_done, prev_todo,
                   task_rate, time_rate,
                   total_est, total_spent,
                   phase_code, phase_desc):
    sys = (
        "You are an academic coach for a CFD master’s thesis titled "
        "'Extreme-wave response of a floating offshore wind turbine for different mooring designs'.\n"
        f"Phase: {phase_code} — {phase_desc}\n"
        "Overall milestones:\n"
        " • P0 (04-22→05-15): 50–200m Stokes5 grid convergence (<3%)\n"
        " • P1 (05-16→06-10): NewWave focusing wave + draft\n"
        " • P2 (06-11→07-01): Wind-wave coupling + reflection (<2%)\n"
        " • P3 (07-02→07-20): 3D FOWT static blades ×2 moorings\n"
        " • P4 (07-21→08-01): Thesis ≥60p + PPT 20p\n"
        "Resources:\n"
        " • 文献: ~/Documents/01Project/2411Masterarbeit/Resources + Zotero\n"
        " • 仿真案例: ~/Programs/starccm case\n"
    )
    # 2️⃣ User Prompt：动态上下文 + 示例 + 输出限制
    usr = (
      f"昨天完成率 {task_rate:.0%}，时间进度 {time_rate:.0%}；\n"
      f"预计 {total_est:.1f}h，实际 {total_spent:.1f}h。\n"
      "已完成：" + ", ".join(d['text'] for d in prev_done) + "\n"
      "未完成：" + ", ".join(t['text'] for t in prev_todo) + "\n\n"
      "请基于效率：若实际>预计*1.1，则任务减至 1-2 条；"
      "若实际<预计*0.9，则可给 2-3 条稍具挑战性任务。\n"
      "列出 **今日需完成的 1-3 个任务**，格式：\n"
      "• 动词 开头，中文任务描述 (预计 Xh)\n"
      "每条 ≤ 30 字，独立行，无编号。"
    )

    resp=client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[{"role":"system","content":sys},
                  {"role":"user","content":usr}],
        stop=["\n\n"]
    )
    return resp.choices[0].message.content.strip()


# ---------- Logseq 写入 ----------
def append_to_logseq(today_text, task_rate, time_rate,
                     total_est,total_spent, phase_code):
    file=JOURNALS/f"{dt.date.today():%Y_%m_%d}.md"
    file.parent.mkdir(parents=True, exist_ok=True)
    ts=dt.datetime.now().strftime("%H:%M")
    header=(f"\n## GPT 任务 · {ts}\n"
            f"- 阶段：{phase_code}\n"
            f"- 时间进度：{time_rate:.0%}\n"
            f"- 昨日完成率：{task_rate:.0%}\n"
            f"- 昨日预计/实际：{total_est:.1f}h / {total_spent:.1f}h\n")
    bullets="\n".join(f"- TODO {l.strip()}" for l in today_text.splitlines())
    with file.open("a",encoding="utf-8") as f: f.write(header+bullets+"\n")

# ---------- 主流程 ----------
if __name__=="__main__":
    today, yest = dt.date.today(), dt.date.today()-dt.timedelta(days=1)

    done_y, todo_y            = parse_tasks_for_date(yest)
    total_est   = sum(x['est']   for x in done_y + todo_y)
    total_spent = sum(x['dur']   for x in done_y) + \
                  sum(x['spent'] for x in todo_y)          # 🟢 新增

    efficiency  = total_spent / total_est if total_est else 1.0
    task_rate                 = len(done_y)/(len(done_y)+len(todo_y)) if done_y or todo_y else 0
    phase_code, phase_desc    = get_current_phase()
    time_rate                 = get_time_progress(phase_code)

    plan_today = gpt_next_steps(done_y, todo_y,
                                task_rate, time_rate,
                                total_est,total_spent,
                                phase_code, phase_desc)

    append_to_logseq(plan_today, task_rate, time_rate,
                     total_est,total_spent, phase_code)
    print(plan_today)

