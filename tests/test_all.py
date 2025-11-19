import os, unittest, pandas as pd
from backend.storage.db import init_db, get_db
from backend.services.pipeline import RecruitPipeline
from backend.services.invite import write_ics, make_invite_email

class RecruitFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        conn = get_db(); cur = conn.cursor()
        for t in ["score","resume","jd","audit"]:
            cur.execute(f"DELETE FROM {t}")
        conn.commit(); conn.close()

    def test_scoring_pipeline(self):
        pipe = RecruitPipeline()
        df = pd.DataFrame([
            {"id":"1","name":"测试A","email":"a@ex.com","phone":"13800000000","edu":"本科","companies":"在线教育/培训","years":3,"skills":"沟�?转化 CRM 跟进 试听","projects":"转化提升项目","text_raw":""},
            {"id":"2","name":"测试B","email":"b@ex.com","phone":"13900000000","edu":"大专","companies":"外包/客服","years":1,"skills":"客服 行政","projects":"","text_raw":""}
        ])
        pipe.ingest_resumes_df(df)
        scored = pipe.score_all("课程顾问")
        self.assertTrue((scored["score_total"] >= 0).all())
        deduped = pipe.dedup_and_rank(scored)
        self.assertGreaterEqual(len(deduped), 1)

    def test_ics(self):
        path = write_ics("课程顾问-初试","2025-11-15 14:00, Asia/Shanghai",30,"hr@example.com","c@ex.com")
        self.assertTrue(os.path.exists(path))
        self.assertIn("课程顾问", make_invite_email({"name":"小王","skills":"沟�?转化","years":2},"课程顾问"))

if __name__ == "__main__":
    unittest.main()

