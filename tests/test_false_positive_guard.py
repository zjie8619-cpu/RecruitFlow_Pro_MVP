import pytest
from backend.services.text_rules import sanitize_for_job

@pytest.mark.parametrize(
    "job,evidence,summary,expect_ev,expect_sm",
    [
        (
            "课程顾问（销售）",
            "曾获得数学竞赛国家一等奖；精通LaTeX；拥有电销邀约经验；CRM跟进成单显著",
            "教学教研能力突出；获奥赛奖项；销售转化优秀",
            "拥有电销邀约经验；CRM跟进成单显著",
            "销售转化优秀",
        ),
        (
            "竞赛教练",
            "指导学生获数学竞赛一等奖；多次命题研究；教授LaTeX",
            "有多年竞赛培训经�?,
            "指导学生获数学竞赛一等奖；多次命题研究；教授LaTeX",
            "有多年竞赛培训经�?,
        ),
    ],
)
def test_guard(job, evidence, summary, expect_ev, expect_sm):
    ev, sm = sanitize_for_job(job, evidence, summary)
    assert ev == expect_ev
    assert sm == expect_sm

