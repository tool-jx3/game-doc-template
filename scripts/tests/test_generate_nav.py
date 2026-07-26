import generate_nav as gn
from generate_nav import first_file_description


class TestFirstFileDescriptionRecursive:
    def test_flat_files(self):
        section = {
            "files": {
                "index": {"order": 0, "description": "Overview", "pages": [1, 1]},
                "combat": {"order": 1, "description": "Combat rules", "pages": [2, 3]},
            }
        }
        assert first_file_description(section) == "Overview"

    def test_nested_finds_leaf(self):
        section = {
            "files": {
                "combat": {
                    "order": 0,
                    "files": {
                        "actions": {"order": 0, "description": "Action rules", "pages": [1, 2]},
                    },
                },
            }
        }
        assert first_file_description(section) == "Action rules"

    def test_empty_files(self):
        assert first_file_description({"files": {}}) == ""

    def test_no_description_returns_empty(self):
        section = {"files": {"index": {"order": 0, "pages": [1, 1]}}}
        assert first_file_description(section) == ""


class TestGenerateIndexNestedLinks:
    def test_hero_links_resolve_to_first_leaf(self):
        chapters = {
            "core-rules": {
                "title": "Core Rules",
                "order": 1,
                "files": {
                    "combat": {
                        "title": "Combat",
                        "order": 0,
                        "files": {
                            "actions": {"order": 0, "pages": [5, 7], "description": "Action rules"},
                        },
                    },
                },
            },
            "expansion": {
                "title": "Expansion",
                "order": 2,
                "files": {
                    "new-classes": {"order": 0, "pages": [1, 8], "description": "New classes"},
                },
            },
        }
        style = {"site": {"title": "Test", "description": "Test site"}}
        result = gn.generate_index(chapters, style)
        assert "/core-rules/combat/actions/" in result
        assert 'href="/core-rules/combat/actions/"' in result

    def test_hero_links_flat_files_unchanged(self):
        chapters = {
            "combat": {
                "title": "Combat",
                "order": 1,
                "files": {
                    "index": {"order": 0, "pages": [1, 2], "description": "Combat rules"},
                },
            },
        }
        style = {"site": {"title": "Test"}}
        result = gn.generate_index(chapters, style)
        assert "/combat/index/" in result or "/combat/" in result


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

    def test_uses_primary_file_route_for_sections_without_index(self):
        chapters = {
            "combat": {
                "title": "戰鬥",
                "order": 1,
                "files": {
                    "maps-and-zones": {
                        "title": "地圖與區域",
                        "order": 0,
                        "description": "戰鬥地圖與區域規則",
                    },
                    "actions": {
                        "title": "行動",
                        "order": 1,
                        "description": "戰鬥行動規則",
                    },
                },
            },
            "travel": {
                "title": "旅行",
                "order": 2,
                "files": {
                    "travel-rules": {
                        "title": "旅行規則",
                        "order": 0,
                        "description": "旅行與移動規則",
                    },
                },
            },
        }

        result = gn.generate_index(chapters, {}, mode="bilingual")

        assert "      link: /bilingual/combat/maps-and-zones/" in result
        assert '  <LinkCard title="戰鬥" href="/bilingual/combat/maps-and-zones/" description="戰鬥地圖與區域規則" />' in result
        assert '  <LinkCard title="旅行" href="/bilingual/travel/travel-rules/" description="旅行與移動規則" />' in result


class TestGenerateSidebarEntries:
    def test_single_file_section_becomes_direct_slug_link(self):
        chapters = {
            "introduction": {
                "title": "簡介",
                "order": 1,
                "files": {
                    "index": {
                        "title": "簡介",
                        "order": 0,
                    }
                },
            },
            "combat": {
                "title": "戰鬥",
                "order": 2,
                "files": {
                    "maps-and-zones": {
                        "title": "地圖與區域",
                        "order": 0,
                    },
                    "actions": {
                        "title": "行動",
                        "order": 1,
                    },
                },
            },
        }

        result = gn.generate_sidebar_entries(chapters, mode="bilingual")

        assert "label: '簡介'" in result
        assert "slug: 'bilingual/introduction'" in result
        assert "autogenerate: { directory: 'bilingual/combat' }" in result
        assert "autogenerate: { directory: 'bilingual/introduction' }" not in result

    def test_single_group_with_multiple_leaves_stays_autogenerate(self):
        chapters = {
            "core": {
                "title": "核心規則",
                "order": 1,
                "files": {
                    "combat": {
                        "title": "戰鬥",
                        "order": 0,
                        "files": {
                            "actions": {
                                "title": "行動",
                                "order": 0,
                                "pages": [1, 2],
                            },
                            "damage": {
                                "title": "傷害",
                                "order": 1,
                                "pages": [3, 4],
                            },
                        },
                    },
                },
            },
        }

        result = gn.generate_sidebar_entries(chapters)

        assert "label: '核心規則'" in result
        assert "autogenerate: { directory: 'core' }" in result
        assert "slug: 'core/combat/actions'" not in result
