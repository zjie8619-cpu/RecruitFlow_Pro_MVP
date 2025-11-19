import argparse, time
from backend.services.pipeline import RecruitPipeline
from backend.services.reporting import export_round_report
from backend.storage.db import init_db

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, help="岗位名称，如：课程顾�?)
    parser.add_argument("--topn", type=int, default=10)
    args = parser.parse_args()

    init_db()
    pipe = RecruitPipeline()
    start = time.time()
    scored  = pipe.score_all(args.job)
    deduped = pipe.dedup_and_rank(scored).head(args.topn)
    path = export_round_report(deduped)
    print(f"完成一轮评分与导出：{path} | 候�?{len(deduped)} | 用时 {time.time()-start:.2f}s")

if __name__ == "__main__":
    main()

