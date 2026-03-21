import generate_nav as gn


class TestGenerateIndex:
    def test_yaml_quotes_frontmatter_strings_with_colons(self):
        chapters = {
            "quick-start": {
                "title": "快速開始：玩家",
                "order": 1,
                "files": {
                    "index": {
                        "order": 1,
                        "description": "從這裡開始：建立角色",
                    }
                },
            },
            "gm-guide": {
                "title": "主持人：指南",
                "order": 2,
                "files": {},
            },
        }
        style = {
            "site": {
                "title": "測試站：首頁",
                "description": "規則整理：快速導覽",
                "tagline": "查閱：規則、角色與裝備",
            }
        }

        result = gn.generate_index(chapters, style)

        assert 'title: "測試站：首頁"' in result
        assert 'description: "規則整理：快速導覽"' in result
        assert '  tagline: "查閱：規則、角色與裝備"' in result
        assert '    - text: "快速開始：玩家"' in result
        assert '    - text: "主持人：指南"' in result
