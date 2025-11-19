import pandas as pd
from backend.storage.db import init_db
from backend.services.pipeline import RecruitPipeline

def main():
    init_db()
    df = pd.read_csv("data/samples/sample_resumes.csv")
    pipe = RecruitPipeline()
    pipe.ingest_resumes_df(df)
    for job in ["课程顾问","教学运营专员","教研编辑"]:
        jd_long, jd_short, rubric = pipe.generate_jd(job)
        pipe.save_jd(job, jd_long, jd_short, rubric)
    print("Seed 完成：样例简历入�?& JD 生成�?)

if __name__ == "__main__":
    main()

