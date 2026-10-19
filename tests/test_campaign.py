import json
from http.server import ThreadingHTTPServer
import threading
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from modules.campaign import CampaignRunner, NeedsAttention, RunControl, Stopped, TaskUnavailable, load_config, validate_config
from modules.control_panel import Controller, LocalHTTPServer, make_handler, serve
from modules.device_adapter import DeviceAdapter
from modules.screen_reader import Screen, ScreenReader
from modules.task_model import TextNode, is_task_list, normalize, parse_tasks


def node(text, x, y, width=400, height=65):
    return TextNode(text, (x, y, x + width, y + height))


def task_screen(progress=0, package='com.taobao.taobao', action='去完成'):
    return Screen([node('做任务赚能量', 500, 630), node('累计任务奖励', 60, 800),
                   node(f'当前进度 {progress}/50', 60, 900),
                   node(f'好物随心逛（{progress}/10）', 260, 1110, 700),
                   node('浏览15秒 +400', 260, 1190), node(action, 1150, 1140, 220)],
                  1440, 3200, package)


class RecognitionTests(unittest.TestCase):
    def test_flash_coupon_visit_is_not_an_order_requirement(self):
        screen = task_screen()
        screen.nodes[3].text = '领闪购红包下单直接省(0/1)'
        screen.nodes[4].text = '点击去逛+600'
        task = parse_tasks(screen.nodes)[0]
        self.assertEqual(task.kind, 'visit')
        self.assertFalse(task.target_app)
        screen.nodes[4].text = '完成下单后领奖'
        self.assertEqual(parse_tasks(screen.nodes)[0].kind, 'manual')

    def test_games_invitations_and_exams_are_explicitly_excluded(self):
        for title in ('去玩趣味小游戏(0/3)玩1款游戏得+600', '每拉1人最高2000能量(0/10)',
                      '淘金币等级考试(0/1)', '去玩抽奖游戏(0/1)'):
            screen = task_screen()
            screen.nodes[3].text = title
            task = parse_tasks(screen.nodes)[0]
            self.assertEqual(task.kind, 'manual')
            self.assertTrue(task.skip_reason.startswith('已跳过'))

    def test_alipay_draw_promotion_with_jump_contract_is_only_a_visit(self):
        screen = task_screen()
        screen.nodes[3].text = '去支付宝抽1000元红包(0/1)跳转得+400'
        screen.nodes[4].text = ''
        task = parse_tasks(screen.nodes)[0]
        self.assertEqual(task.kind, 'visit')
        self.assertEqual(task.target_app, '支付宝')
        screen.nodes[3].text = '去支付宝抽1000元红包(0/1)'
        screen.nodes[4].text = '完成抽奖一次'
        self.assertEqual(parse_tasks(screen.nodes)[0].kind, 'manual')

    def test_app_metadata_does_not_presume_whether_it_is_installed(self):
        screen = task_screen()
        screen.nodes[3].text = '去微博看看热搜(0/1)跳转得奖励+400'
        screen.nodes[4].text = ''
        task = parse_tasks(screen.nodes)[0]
        self.assertEqual(task.kind, 'visit')
        self.assertEqual(task.title, '去微博看看热搜')
        self.assertIn('com.sina.weibo', task.target_packages)
        self.assertEqual(task.skip_reason, '')

    def test_claimed_header_is_not_a_task_row(self):
        screen = task_screen()
        screen.nodes.append(node('已领取', 900, 810, 250))
        self.assertEqual(len(parse_tasks(screen.nodes)), 1)

    def test_progress_duration_and_button_pair(self):
        screen = task_screen(3)
        tasks = parse_tasks(screen.nodes, 1440, 3200)
        self.assertTrue(is_task_list(screen.nodes))
        self.assertEqual(len(tasks), 1)
        self.assertEqual((tasks[0].title, tasks[0].current, tasks[0].total, tasks[0].seconds),
                         ('好物随心逛', 3, 10, 15))
        self.assertEqual(tasks[0].kind, 'browse')

    def test_unicode_and_spaces(self):
        self.assertEqual(normalize(' 浏览 ５ 秒（１／１０） '), '浏览5秒(1/10)')

    def test_stable_identity_across_progress_and_ocr(self):
        one = parse_tasks(task_screen(0).nodes)[0]
        two = parse_tasks(task_screen(2).nodes)[0]
        self.assertEqual(one.key, two.key)

    def test_aggregated_accessibility_row_matches_ocr_identity(self):
        ocr = parse_tasks(task_screen(0).nodes)[0]
        screen = task_screen(1)
        screen.nodes[3].text = '好物随心逛(1/10) 浏览15秒 +400'
        ui = parse_tasks(screen.nodes)[0]
        self.assertEqual(ui.key, ocr.key)
        self.assertEqual(ui.seconds, 15)

    def test_single_aggregated_row_preserves_duration(self):
        screen = task_screen(1)
        screen.nodes[3].text = '拍立淘逛感兴趣的宝贝(1/5)浏览5秒+400'
        del screen.nodes[4]
        task = parse_tasks(screen.nodes)[0]
        self.assertEqual(task.title, '拍立淘逛感兴趣的宝贝')
        self.assertEqual(task.seconds, 5)
        self.assertIn('浏览5秒', task.detail)

    def test_aggregated_modal_row_ignores_obscured_homepage(self):
        for title, expected in [('好物沉浸看(0/10)浏览15秒+400', 'browse'),
                                ('逛一逛支付宝农场(0/1)点击去逛+600', 'visit'),
                                ('拍立淘逛感兴趣的宝贝(0/5)浏览5秒+400', 'browse')]:
            screen = task_screen()
            screen.nodes[3].text = title
            screen.nodes[4].text = '淘宝闪购 下单得500 电竞游戏鼠标'
            task = parse_tasks(screen.nodes)[0]
            self.assertEqual(task.kind, expected)
            self.assertNotIn('下单', task.detail)

    def test_repeated_caption_is_description_not_part_of_task_identity(self):
        screen = task_screen()
        screen.nodes[3].text = '逛一逛蚂蚁庄园(0/1)逛一逛蚂蚁庄园+600'
        task = parse_tasks(screen.nodes)[0]
        self.assertEqual(task.title, '逛一逛蚂蚁庄园')
        self.assertEqual(task.detail, '逛一逛蚂蚁庄园+600')

    def test_alipay_title_is_not_a_payment(self):
        screen = task_screen()
        screen.nodes[3].text = '逛一逛支付宝农场(0/1)'
        screen.nodes[4].text = '点击去逛 +600'
        task = parse_tasks(screen.nodes)[0]
        self.assertEqual(task.kind, 'visit')

    def test_side_effect_tasks_require_manual_handling(self):
        for title in ['下单购买', '充值话费', '关注店铺', '邀请好友', '答题考试', '下载应用', '收藏商品', '开通会员']:
            screen = task_screen()
            screen.nodes[3].text = title + '(0/1)'
            self.assertEqual(parse_tasks(screen.nodes)[0].kind, 'manual', title)

    def test_two_rows_do_not_borrow_each_others_descriptions(self):
        screen = task_screen()
        screen.nodes += [node('逛一逛蚂蚁庄园(0/1)', 260, 1380, 700),
                         node('点击去逛 +600', 260, 1460), node('去完成', 1150, 1410, 220)]
        tasks = parse_tasks(screen.nodes)
        self.assertEqual([(t.kind, t.seconds) for t in tasks], [('browse', 15), ('visit', 0)])

    def test_unlabelled_buttons_are_never_executed(self):
        self.assertEqual(parse_tasks([node('去完成', 1150, 1000, 220)]), [])

    def test_reward_toast_without_progress_is_not_a_task(self):
        screen = task_screen()
        screen.nodes[3].text = '好物沉凭务已完成!'
        self.assertEqual(parse_tasks(screen.nodes), [])

    def test_completed_task_not_executable(self):
        self.assertEqual(parse_tasks(task_screen(10).nodes)[0].kind, 'done')

    def test_milestone_claim_supports_accessibility_and_ocr(self):
        for label in ['立即领取', '5次任务，立即领取，奖励1000']:
            screen = task_screen(7)
            screen.nodes.append(node(label, 410, 800, 280, 180))
            tasks = parse_tasks(screen.nodes)
            claim = next(t for t in tasks if t.kind == 'claim')
            self.assertTrue(claim.key.startswith('milestone-'))

    def test_unrelated_claim_outside_reward_panel_is_not_a_milestone(self):
        screen = task_screen()
        screen.nodes.append(node('立即领取', 300, 2400, 260))
        self.assertFalse(any(t.key.startswith('milestone-') for t in parse_tasks(screen.nodes)))

    def test_harmony_hierarchy_attributes(self):
        reader = ScreenReader(Mock())
        nodes = reader._flatten({'attributes': {'text': '任务', 'bounds': '[1,2][30,40]'},
                                 'children': [{'attributes': {'text': '去完成', 'bounds': '[50,2][90,40]'}}]})
        self.assertEqual([n.text for n in nodes], ['任务', '去完成'])


class RunnerTests(unittest.TestCase):
    def test_kind_selection_skips_without_clicking_and_does_not_persist(self):
        r = self.clock_runner()
        screen = task_screen()
        r.config['enabled_task_kinds'] = ['search']
        r.ensure_list = Mock(return_value=screen)
        r.read = Mock(return_value=screen)
        self.assertEqual(r.run()['attempts'], 0)
        r.device.click.assert_not_called()
        self.assertIn('本轮未选择', next(iter(r.records.values()))['reason'])
        self.assertFalse(r.unavailable_tasks)
        fresh = CampaignRunner(r.device, unavailable_tasks=r.unavailable_tasks)
        fresh.remember(fresh.tasks(screen))
        self.assertEqual(next(iter(fresh.records.values()))['status'], 'pending')

    def test_kind_selection_rejects_empty_unknown_and_duplicate_values(self):
        for invalid in ([], ['manual'], ['browse', 'browse'], 'browse', [None]):
            config = load_config()
            config['enabled_task_kinds'] = invalid
            with self.assertRaises(ValueError):
                validate_config(config)

    def test_auto_entry_waits_for_restored_task_after_transient_splash(self):
        r = self.clock_runner()
        home = Screen([], 1440, 3200, 'com.miui.home')
        splash = Screen([], 1440, 3200, 'com.taobao.taobao')
        restored = task_screen()
        r.read = Mock(side_effect=[home, splash, restored])
        self.assertIs(r.ensure_list(auto_open=True), restored)
        r.device.resume_app.assert_called_once_with('com.taobao.taobao')
        self.assertEqual(r.origin, 'com.taobao.taobao')

    def clock_runner(self):
        r = self.runner()
        clock = [0.0]
        r.control.now = lambda: clock[0]
        r.control.wait.side_effect = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
        return r

    def search_page(self, query='搜索'):
        screen = Screen([node('搜索', 210, 160, 860, 123), node('搜索', 1190, 164, 200, 115),
                         node('历史搜索', 40, 355), node('搜索发现', 40, 750),
                         node('手机壳', 300, 900, 200)], 1440, 3200, 'com.taobao.taobao')
        tree = {'children': [dict(type='android.widget.EditText', text=query, hint='搜索', focused='true',
                                  bounds='[210,160][1070,283]'),
                             dict(type='android.widget.Button', text='搜索', id='searchbtn',
                                  bounds='[1190,164][1390,279]')]}
        return screen, tree

    def results_page(self):
        return Screen([node(t, 40, 300 + i * 90) for i, t in enumerate(
            ['综合', '销量,未选中', '筛选', '手机壳', '包邮', '¥15', '100人付款', '商品列表'])],
                      1440, 3200, 'com.taobao.taobao')

    def test_embedded_campaign_search_grid_without_sort_toolbar(self):
        screen = Screen([node('浏览15秒可领400', 700, 160),
                         node('搜索', 1180, 350, 200), node('a', 180, 350),
                         node('商品甲', 30, 1300), node('¥21.68', 30, 1450),
                         node('金币热卖价', 300, 1450), node('商品乙', 760, 1300),
                         node('¥448.23', 760, 1450)], 1440, 3200, 'com.taobao.taobao')
        self.assertTrue(CampaignRunner.search_results_ready(screen))
        screen.nodes = screen.nodes[:3] + [node('历史搜索', 30, 600), node('搜索发现', 30, 1100)]
        self.assertFalse(CampaignRunner.search_results_ready(screen))

    def test_search_types_then_clicks_button_not_identical_edit_label(self):
        r = self.clock_runner()
        screen, tree = self.search_page()
        r.device.dump_hierarchy.return_value = tree
        r.read = Mock(return_value=self.results_page())
        self.assertTrue(r.handle_search(screen))
        r.device.click.assert_called_once_with(1290, 221)
        r.device.input_text.assert_called_once_with('手机壳')
        r.device.clear_text.assert_not_called()

    def test_existing_query_is_submitted_without_retyping(self):
        r = self.clock_runner()
        screen, tree = self.search_page('phone')
        r.device.dump_hierarchy.return_value = tree
        r.read = Mock(return_value=self.results_page())
        self.assertTrue(r.handle_search(screen))
        r.device.click.assert_called_once_with(1290, 221)
        r.device.input_text.assert_not_called()

    def test_search_relocates_submit_after_input_expands_reward_header(self):
        r = self.clock_runner()
        screen, tree = self.search_page()
        moved = json.loads(json.dumps(tree))
        moved['children'][1]['bounds'] = '[1190,264][1390,379]'
        r.device.dump_hierarchy.side_effect = [tree, moved]
        r.read = Mock(return_value=self.results_page())
        self.assertTrue(r.handle_search(screen))
        r.device.click.assert_called_once_with(1290, 321)

    def test_browse_caption_on_search_landing_submits_before_browsing(self):
        r = self.clock_runner()
        before = task_screen()
        landing, _ = self.search_page()
        r.read = Mock(return_value=landing)
        r.handle_search = Mock(return_value=True)
        r.recover = Mock(return_value=task_screen(1))
        r.execute(r.tasks(before)[0], before)
        r.handle_search.assert_called_once_with(landing)

    def test_search_can_use_ascii_when_there_are_no_suggestions(self):
        r = self.clock_runner()
        screen, tree = self.search_page()
        screen.nodes.pop()
        r.device.dump_hierarchy.return_value = tree
        r.read = Mock(return_value=self.results_page())
        self.assertTrue(r.handle_search(screen))
        r.device.input_text.assert_called_once_with('a')

    def test_failed_search_submission_is_bounded_and_not_browsed(self):
        r = self.clock_runner()
        screen, tree = self.search_page('phone')
        r.device.dump_hierarchy.return_value = tree
        r.read = Mock(return_value=screen)
        self.assertFalse(r.handle_search(screen))
        r.device.click.assert_called_once_with(1290, 221)
        r.device.swipe.assert_not_called()

    def test_missing_apps_are_tried_once_then_skipped_across_runs(self):
        r = self.clock_runner()
        screen = task_screen()
        screen.nodes[3].text = '去微博看看热搜(0/1)'
        screen.nodes[4].text = '跳转得奖励+400'
        screen.nodes += [node('去快手打卡领手机(0/1)', 260, 1380, 700),
                         node('点击去逛+600', 260, 1460), node('去完成', 1150, 1410, 220)]
        r.device.installed_packages.return_value = set()
        r.remember(r.tasks(screen))
        self.assertTrue(all(t['status'] == 'pending' for t in r.records.values()))
        r.device.installed_packages.assert_not_called()
        r.ensure_list = Mock(return_value=screen)
        r.read = Mock(return_value=screen)
        r.recover = Mock(return_value=screen)
        result = r.run()
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['skipped'], 2)
        self.assertEqual(r.device.click.call_count, 2)
        self.assertTrue(all(t['status'] == 'disabled' for t in r.records.values()))
        # The panel passes only this phone's runtime evidence into the next run.
        again = CampaignRunner(r.device, unavailable_tasks=r.unavailable_tasks)
        again.ensure_list = Mock(return_value=screen)
        again.read = Mock(return_value=screen)
        again.control.wait = Mock()
        self.assertEqual(again.run()['attempts'], 0)
        self.assertEqual(r.device.click.call_count, 2)
        # Another user's fresh session starts with no inherited conclusions.
        other = CampaignRunner(Mock())
        other.remember(other.tasks(screen))
        self.assertTrue(all(t['status'] == 'pending' for t in other.records.values()))

    def test_installing_app_reenables_previously_missing_task(self):
        r = self.runner()
        screen = task_screen()
        screen.nodes[3].text = '去微博看看热搜(0/1)'
        r.unavailable_tasks['app:微博'] = '未安装微博，已跳过'
        r.device.installed_packages.return_value = {'com.sina.weibo'}
        r.remember(r.tasks(screen))
        self.assertEqual(next(iter(r.records.values()))['status'], 'pending')
        self.assertFalse(r.unavailable_tasks)

    def test_silent_failed_jump_checks_this_phone_and_skips_without_retry(self):
        r = self.runner()
        screen = task_screen()
        screen.nodes[3].text = '去快手打卡领手机(0/1)'
        r.device.installed_packages.return_value = set()
        r.ensure_list = Mock(return_value=screen)
        r.execute = Mock(return_value=(screen, False, False))
        r.read = Mock(return_value=screen)
        result = r.run()
        self.assertEqual(result['attempts'], 1)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(next(iter(r.records.values()))['status'], 'disabled')
        self.assertIn('未安装快手', next(iter(r.records.values()))['reason'])

    def test_market_failure_stays_skipped_even_when_app_is_installed(self):
        r = self.runner()
        screen = task_screen()
        screen.nodes[3].text = '去微博看看热搜(0/1)'
        r.device.installed_packages.return_value = {'com.sina.weibo'}
        r.unavailable_tasks['app:微博'] = '目标应用不可用或跳转到安装页，已跳过'
        r.remember(r.tasks(screen))
        r.remember(r.tasks(screen))
        self.assertEqual(next(iter(r.records.values()))['status'], 'disabled')
        r.device.installed_packages.assert_not_called()

    def test_download_page_is_terminal_without_clicking_install(self):
        r = self.runner()
        with self.assertRaises(TaskUnavailable):
            r.check_destination(Screen([node('立即下载', 100, 500)], 1440, 3200, r.origin))
        r.device.click.assert_not_called()

    def test_milestone_requires_received_label_in_its_own_card(self):
        r = self.runner()
        before = task_screen(7)
        before.nodes.append(node('立即领取', 1080, 800, 250, 120))
        claim = next(t for t in r.tasks(before) if t.kind == 'claim')
        empty = task_screen(7)
        self.assertFalse(r.verify(claim, before, empty, explicit=True))
        wrong_card = task_screen(7)
        wrong_card.nodes.append(node('已领取', 420, 800, 250, 120))
        self.assertFalse(r.verify(claim, before, wrong_card))
        received = task_screen(7)
        received.nodes.append(node('50次任务，已领取，奖励4000', 1080, 800, 250, 120))
        self.assertTrue(r.verify(claim, before, received))

    def runner(self):
        device = Mock()
        device.device_type = 'uiautomator2'
        runner = CampaignRunner(device)
        runner.origin = 'com.taobao.taobao'
        runner.control.wait = Mock()
        return runner

    def test_waiting_is_not_success(self):
        r = self.runner()
        before = task_screen()
        task = parse_tasks(before.nodes)[0]
        self.assertFalse(r.verify(task, before, before))
        self.assertFalse(r.verify(task, before, before, explicit=True))
        self.assertTrue(r.verify(task, before, task_screen(1)))

    def test_rotating_caption_keeps_same_retry_identity(self):
        r = self.runner()
        first = r.tasks(task_screen(0))[0]
        changed = task_screen(1)
        changed.nodes[3].text = '逛逛去屑洗发水(1/10)'
        second = r.tasks(changed)[0]
        self.assertEqual(first.key, second.key)
        self.assertTrue(r.verify(first, task_screen(0), changed))

    def test_completed_rotating_caption_keeps_same_identity(self):
        r = self.runner()
        first = r.tasks(task_screen(10))[0]
        changed = task_screen(10)
        changed.nodes[3].text = '看看#沙发(10/10)'
        self.assertEqual(first.key, r.tasks(changed)[0].key)

    def test_final_row_removed_is_verified_only_between_visible_neighbours(self):
        r = self.runner()
        before = task_screen(4)
        before.nodes[3].text = '搜一搜你喜欢的宝贝(4/5)'
        before.nodes += [node('去快手打卡(0/1)', 260, 850, 700), node('去完成', 1150, 880, 220),
                         node('每拉1人得奖励(0/10)', 260, 1380, 700), node('去完成', 1150, 1410, 220)]
        task = next(t for t in r.tasks(before) if t.kind == 'search')
        after = Screen([n for n in before.nodes if n not in before.nodes[3:6]], 1440, 3200, r.origin)
        after.nodes = [TextNode(n.text, tuple(v - 270 if i % 2 and n.bounds[1] >= 1380 else v
                                             for i, v in enumerate(n.bounds))) for n in after.nodes]
        self.assertTrue(r.verify(task, before, after))
        clipped = Screen([n for n in after.nodes if n.bounds[1] < 1000], 1440, 3200, r.origin)
        self.assertFalse(r.verify(task, before, clipped))
        task.current = 3
        self.assertFalse(r.verify(task, before, after))

    def offer_screen(self, title, progress, counter):
        screen = task_screen(counter)
        screen.nodes[3].text = f'{title}({progress}/1)'
        screen.nodes[4].text = '点击去逛+600'
        screen.nodes.append(node('O1CN-shared-slot-icon', 40, 1110, 140))
        return screen

    def test_replacement_offer_reusing_icon_has_a_fresh_retry_budget(self):
        r = self.runner()
        first = r.tasks(self.offer_screen('领闪购红包下单直接省', 0, 49))[0]
        r.failures[(first.key, 0)] = r.config['max_attempts']
        replacement = r.tasks(self.offer_screen('去支付宝抽1000元红包', 0, 50))[0]
        self.assertNotEqual(first.key, replacement.key)
        self.assertEqual(r.failures[(replacement.key, 0)], 0)

    def test_new_offer_is_executed_in_the_same_run(self):
        r = self.runner()
        first = self.offer_screen('领闪购红包下单直接省', 0, 49)
        replacement = self.offer_screen('去支付宝抽1000元红包', 0, 50)
        done = self.offer_screen('去支付宝抽1000元红包', 1, 50)
        r.ensure_list = Mock(return_value=first)
        r.execute = Mock(side_effect=[(replacement, False, False), (done, False, True)])
        r.read = Mock(return_value=done)
        result = r.run()
        self.assertEqual(result['completed'], 2)
        self.assertEqual([call.args[0].title for call in r.execute.call_args_list],
                         ['领闪购红包下单直接省', '去支付宝抽1000元红包'])

    def test_first_visit_removed_requires_visual_header_and_two_shifted_rows(self):
        r = self.runner()
        before = self.offer_screen('去支付宝抽1000元红包', 0, 50)
        before.nodes += [node('去微博看看热搜(0/1)', 260, 1380, 700), node('去完成', 1150, 1410, 220),
                         node('去快手打卡(0/1)', 260, 1650, 700), node('去完成', 1150, 1680, 220)]
        task = r.tasks(before)[0]
        after = Screen([n for n in before.nodes if n not in before.nodes[3:7]], 1440, 3200, r.origin, 'ocr')
        after.nodes = [TextNode(n.text, tuple(v - 270 if i % 2 and n.bounds[1] >= 1380 else v
                                             for i, v in enumerate(n.bounds))) for n in after.nodes]
        self.assertTrue(r.verify(task, before, after))
        after.source = 'ui'
        self.assertFalse(r.verify(task, before, after))
        after.source = 'ocr'
        after.nodes = [n for n in after.nodes if n.text != '累计任务奖励']
        self.assertFalse(r.verify(task, before, after))

    def test_cross_app_resume_then_reopen_panel_without_extra_back(self):
        r = self.runner()
        external = Screen([node('蚂蚁庄园', 0, 0)], 1440, 3200, 'com.eg.android.AlipayGphone')
        home = Screen([node('赚能量', 1150, 1200)], 1440, 3200, r.origin)
        r.read = Mock(side_effect=[external, home, task_screen(1)])
        self.assertTrue(is_task_list(r.recover().nodes))
        r.device.resume_app.assert_called_once_with(r.origin)
        r.device.click.assert_called_once()
        r.device.go_back.assert_not_called()

    def test_failed_progress_has_bounded_attempts(self):
        r = self.runner()
        screen = task_screen()
        r.config.update(max_attempts=2, max_tasks=10, max_scroll_pages=1)
        r.read = Mock(return_value=screen)
        r.ensure_list = Mock(return_value=screen)
        r.execute = Mock(return_value=(screen, False, False))
        result = r.run()
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(result['completed'], 0)
        self.assertEqual(result['failed'], 1)

    def test_stop_prevents_next_click(self):
        r = self.runner()
        r.control.stopped.set()
        with self.assertRaises(Stopped):
            r.execute(parse_tasks(task_screen().nodes)[0], task_screen())
        r.device.click.assert_not_called()

    def scrolling_runner(self):
        r = self.runner()
        clock = [0.0]
        r.control.now = lambda: clock[0]
        r.control.wait.side_effect = lambda seconds: clock.__setitem__(0, clock[0] + seconds)
        r.device.swipe.side_effect = lambda *args, **kwargs: clock.__setitem__(0, clock[0] + .45)
        destination = Screen([node('浏览15秒可领400', 800, 200), node('商品列表', 50, 500)], 1440, 3200, r.origin)
        r.read = Mock(return_value=destination)
        r.recover = Mock(return_value=task_screen(1))
        return r, clock, destination

    def test_extended_browse_keeps_scrolling_in_both_directions(self):
        r, clock, _ = self.scrolling_runner()
        before = task_screen()
        r.execute(r.tasks(before)[0], before)
        self.assertGreaterEqual(clock[0], 27)
        self.assertGreater(r.device.swipe.call_count, 20)
        gestures = [call.args for call in r.device.swipe.call_args_list]
        self.assertTrue(any(g[1] > g[3] for g in gestures))
        self.assertTrue(any(g[1] < g[3] for g in gestures))

    def test_completion_hint_ends_extended_browse_early(self):
        r, clock, destination = self.scrolling_runner()
        completed = Screen([node('任务已完成', 800, 200), node('商品列表', 50, 500)], 1440, 3200, r.origin)
        r.read.side_effect = lambda **kwargs: completed if clock[0] >= 8 else destination
        before = task_screen()
        _, explicit, _ = r.execute(r.tasks(before)[0], before)
        self.assertTrue(explicit)
        self.assertLess(clock[0], 27)

    def test_risk_page_requires_human(self):
        r = self.runner()
        for label in ['请完成安全验证', '请输入验证码', '立即登录', '确认支付']:
            with self.assertRaises(NeedsAttention):
                r.guard(Screen([node(label, 0, 0)], 1440, 3200, r.origin))
        r.guard(Screen([node('逛一逛支付宝农场', 0, 0)], 1440, 3200, r.origin))

    def test_stop_is_responsive_while_paused(self):
        control = RunControl()
        control.paused.set()
        control.stopped.set()
        with self.assertRaises(Stopped):
            control.check()

    def test_invalid_or_unbounded_configuration_rejected(self):
        for key, bad in [('max_attempts', 100), ('max_tasks', 0), ('ocr', 'true'), ('max_tasks', 1.5)]:
            config = load_config()
            config[key] = bad
            with self.assertRaises(ValueError):
                validate_config(config)


class NativeInputTests(unittest.TestCase):
    def test_inaccessible_focus_uses_unique_native_edit_without_ime_changes(self):
        from uiautomator2.exceptions import UiObjectNotFoundError
        adapter = DeviceAdapter.__new__(DeviceAdapter)
        adapter.device_type = 'uiautomator2'
        focused, edit = Mock(), Mock()
        edit.count = 1
        focused.set_text.side_effect = UiObjectNotFoundError(-32001, 'missing focus')
        adapter._device = Mock(side_effect=lambda **kwargs: focused if 'focused' in kwargs else edit)
        adapter.input_text('手机壳')
        edit.set_text.assert_called_once_with('手机壳')
        adapter._device.shell.assert_not_called()
        adapter._device.set_input_ime.assert_not_called()
        adapter._device.send_keys.assert_not_called()

    def test_ambiguous_native_edits_do_not_receive_fallback_input(self):
        from uiautomator2.exceptions import UiObjectNotFoundError
        adapter = DeviceAdapter.__new__(DeviceAdapter)
        adapter.device_type = 'uiautomator2'
        focused, edit = Mock(), Mock()
        edit.count = 2
        focused.set_text.side_effect = UiObjectNotFoundError(-32001, 'missing focus')
        adapter._device = Mock(side_effect=lambda **kwargs: focused if 'focused' in kwargs else edit)
        with self.assertRaises(UiObjectNotFoundError):
            adapter.input_text('a')
        edit.set_text.assert_not_called()
        adapter._device.shell.assert_not_called()

    def test_android_text_input_never_uses_or_changes_an_ime(self):
        adapter = DeviceAdapter.__new__(DeviceAdapter)
        adapter.device_type = 'uiautomator2'
        adapter._device = Mock()
        adapter.input_text('手机壳')
        adapter._device.assert_called_with(focused=True)
        adapter._device.return_value.set_text.assert_called_once_with('手机壳')
        adapter.clear_text()
        self.assertEqual(adapter._device.return_value.set_text.call_args.args, ('',))
        adapter._device.send_keys.assert_not_called()
        adapter._device.clear_text.assert_not_called()
        adapter._device.set_input_ime.assert_not_called()
        adapter._device.shell.assert_not_called()


class LocalServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller = Controller()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(cls.controller, 'test-token'))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def test_local_page_and_state(self):
        with urlopen(self.base + '/') as response:
            self.assertIn('双11'.encode(), response.read())
        with urlopen(self.base + '/api/state') as response:
            state = json.load(response)
            self.assertEqual(state['token'], 'test-token')

    def test_health_and_duplicate_launch(self):
        with urlopen(self.base + '/api/health') as response:
            self.assertEqual(json.load(response)['app'], 'miao-task')
        # Returns immediately instead of creating another worker/server.
        reused = serve(self.server.server_port, open_browser=False)
        self.assertIsNone(reused.thread)

    def test_windows_port_cannot_be_bound_twice(self):
        server = LocalHTTPServer(('127.0.0.1', 0), make_handler(Controller(), 'test-token'))
        try:
            with self.assertRaises(OSError):
                duplicate = LocalHTTPServer(('127.0.0.1', server.server_port), make_handler(Controller(), 'test-token'))
                duplicate.server_close()
        finally:
            server.server_close()

    def test_missing_token_cannot_control_phone(self):
        request = Request(self.base + '/api/run', data=b'{}', method='POST')
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 403)

    def test_foreign_origin_cannot_control_phone(self):
        request = Request(self.base + '/api/run', data=b'{}', method='POST',
                          headers={'X-Miao-Token': 'test-token', 'Origin': 'https://example.org'})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 403)

    def test_same_origin_browser_can_apply_settings(self):
        request = Request(self.base + '/api/configure', data=b'{}', method='POST', headers={
            'Content-Type': 'application/json', 'X-Miao-Token': 'test-token',
            'Origin': self.base, 'Sec-Fetch-Site': 'same-origin'})
        with urlopen(request) as response:
            self.assertEqual(response.status, 202)

    def test_run_requires_connection(self):
        request = Request(self.base + '/api/run', data=b'{}', method='POST',
                          headers={'X-Miao-Token': 'test-token'})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 400)

    def test_single_worker_owns_device(self):
        controller = Controller()
        controller.thread = Mock()
        controller.thread.is_alive.return_value = True
        with self.assertRaises(ValueError):
            controller.dispatch('scan', {})

    def test_apply_settings_does_not_start_phone_worker(self):
        controller = Controller()
        controller.dispatch('configure', {'config': {'max_tasks': 20}})
        self.assertEqual(controller.snapshot()['config']['max_tasks'], 20)
        self.assertIsNone(controller.thread)


if __name__ == '__main__':
    unittest.main()
