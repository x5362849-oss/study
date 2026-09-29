# 天体物理文献每日推送 — 主脚本
# 流程: 抓取 arXiv 新论文 -> 关键词筛选 -> 调用 LLM 按 SKILL.md 标注 -> Server酱推送微信
# 依赖: pip install requests pyyaml
# 用法:
#   python main.py --dry-run          # 只抓取和筛选, 不调用 LLM、不推送 (测试用)
#   python main.py --no-push          # 调用 LLM 生成导读, 保存本地但不推送
#   python main.py                    # 完整流程 (需要 SENDKEY 和 LLM_API_KEY 环境变量)

import argparse
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

ARXIV_API = "http://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
SCRIPT_DIR = Path(__file__).resolve().parent


def load_config():
    cfg_path = SCRIPT_DIR / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_recent_papers(cfg):
    """从 arXiv API 抓取指定分类、最近 N 天的论文。"""
    cats = " OR ".join(f"cat:{c}" for c in cfg["arxiv_categories"])
    max_results = int(cfg.get("max_fetch", 200))
    params = {
        "search_query": f"({cats})",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": max_results,
    }
    print(f"[1/4] 拉取 arXiv {cfg['arxiv_categories']} 最新 {max_results} 条 ...")
    resp = requests.get(ARXIV_API, params=params, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    cutoff = datetime.now(timezone.utc) - timedelta(days=float(cfg.get("days_back", 3)))
    papers = []
    for entry in root.findall("atom:entry", NS):
        published = datetime.fromisoformat(
            entry.find("atom:published", NS).text.replace("Z", "+00:00")
        )
        if published < cutoff:
            continue
        abstract = re.sub(r"\s+", " ", entry.find("atom:summary", NS).text.strip())
        papers.append({
            "title": re.sub(r"\s+", " ", entry.find("atom:title", NS).text.strip()),
            "abstract": abstract,
            "link": entry.find("atom:id", NS).text.strip(),
            "published": published.strftime("%Y-%m-%d"),
            "categories": [c.attrib.get("term") for c in entry.findall("atom:category", NS)],
        })
    print(f"      最近 {cfg.get('days_back', 3)} 天内共 {len(papers)} 篇")
    return papers


def score_paper(paper, topics):
    """按主题关键词给论文打分: 命中标题得 3 分, 命中摘要得 1 分。"""
    text = f"{paper['title']} {paper['abstract']}".lower()
    scores, matched = {}, {}
    for topic in topics:
        s, hits = 0, []
        for kw in topic["keywords"]:
            if kw.lower() in text:
                s += 3 if kw.lower() in paper["title"].lower() else 1
                hits.append(kw)
        scores[topic["name"]] = s
        matched[topic["name"]] = hits
    return scores, matched


def select_papers(papers, cfg):
    """关键词打分 + 取分最高的 top_n 篇。"""
    topics = cfg["topics"]
    print("[2/4] 按课题关键词筛选 ...")
    scored = []
    for p in papers:
        scores, matched = score_paper(p, topics)
        best = max(scores, key=scores.get)
        p["score"] = scores[best]
        p["best_topic"] = best
        p["matched"] = matched[best]
        if p["score"] > 0:
            scored.append(p)
    scored.sort(key=lambda x: -x["score"])
    selected = scored[: int(cfg.get("top_n", 3))]
    print(f"      命中 {len(scored)} 篇, 取前 {len(selected)} 篇:")
    for p in selected:
        print(f"      [{p['score']:>2}分] ({p['best_topic']}) {p['title'][:70]}")
    return selected


def build_prompt(papers, cfg):
    """把 SKILL.md + 论文列表组装成发给 LLM 的完整提示词。"""
    skill_text = (SCRIPT_DIR.parent / "skill" / "SKILL.md").read_text(encoding="utf-8")
    entries = []
    for i, p in enumerate(papers, 1):
        entries.append(
            f"### 论文 {i}\n标题: {p['title']}\n发布: {p['published']}\n"
            f"链接: {p['link']}\n命中课题: {p['best_topic']} (关键词: {', '.join(p['matched'])})\n"
            f"摘要: {p['abstract']}\n"
        )
    return (
        f"{skill_text}\n\n---\n\n"
        f"以下是今天从 arXiv 抓取并筛选出的 {len(papers)} 篇论文, "
        f"请严格按照 SKILL.md 的流程生成今日导读:\n\n" + "\n".join(entries)
    )


def call_llm(prompt, cfg):
    """调用 OpenAI 兼容接口 (默认智谱 GLM)。"""
    api_key = os.environ["LLM_API_KEY"]
    base_url = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
    model = os.environ.get("LLM_MODEL", "glm-4-flash")
    print(f"[3/4] 调用 LLM ({model}) 生成导读 ...")
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(cfg.get("temperature", 0.4)),
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def push_wechat(title, content):
    """通过 Server酱推送到微信。"""
    sendkey = os.environ.get("SENDKEY", "")
    if not sendkey:
        print("!! 未设置 SENDKEY, 跳过推送")
        return False
    print("[4/4] 通过 Server酱推送微信 ...")
    resp = requests.post(
        f"https://sctapi.ftqq.com/{sendkey}.send",
        data={"title": title[:32], "desp": content},
        timeout=60,
    )
    resp.raise_for_status()
    print("      推送完成, 请查看微信『服务号消息』")
    return True


def main():
    parser = argparse.ArgumentParser(description="每日天体物理文献导读")
    parser.add_argument("--dry-run", action="store_true", help="只抓取筛选, 不调 LLM 不推送")
    parser.add_argument("--no-push", action="store_true", help="生成导读但不推送")
    args = parser.parse_args()

    cfg = load_config()
    papers = fetch_recent_papers(cfg)
    selected = select_papers(papers, cfg)

    out_dir = SCRIPT_DIR / "output"
    out_dir.mkdir(exist_ok=True)
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

    if args.dry_run or not selected:
        summary = "\n\n".join(
            f"### {p['title']}\n[{p['best_topic']} {p['score']}分] {p['link']}"
            for p in selected
        ) or "今日无命中文献"
        (out_dir / f"candidates-{today}.md").write_text(summary, encoding="utf-8")
        print(f"~~ dry-run 模式, 筛选结果已存 output/candidates-{today}.md")
        return

    digest = call_llm(build_prompt(selected, cfg), cfg)
    (out_dir / f"digest-{today}.md").write_text(digest, encoding="utf-8")
    print(f"      导读已存 output/digest-{today}.md")

    if not args.no_push:
        push_wechat(f"📚 天体物理文献日报 {today}", digest)


if __name__ == "__main__":
    main()
