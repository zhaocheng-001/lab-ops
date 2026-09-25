"""生成站内提醒的定时任务命令。

用法：
    python manage.py generate_reminders          # 执行一次扫描
    python manage.py generate_reminders --loop 60  # 每 60 秒循环执行
"""
import time

from django.core.management.base import BaseCommand

from apps.notifications.services import run_all_scanners
from apps.reservations.services import auto_update_statuses


class Command(BaseCommand):
    help = "扫描预约数据，生成待审批/待签到/待归还/即将到期/已逾期提醒"

    def add_arguments(self, parser):
        parser.add_argument("--loop", type=int, default=0, help="循环执行的间隔秒数，0 表示只执行一次")

    def handle(self, *args, **options):
        interval = options.get("loop") or 0
        if interval <= 0:
            self._run_once()
            return
        self.stdout.write(self.style.WARNING(f"提醒服务已启动，每 {interval} 秒扫描一次（Ctrl+C 退出）"))
        while True:
            try:
                self._run_once()
                time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("提醒服务已停止"))
                break
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"扫描异常：{exc}")
                time.sleep(interval)

    def _run_once(self):
        advanced = auto_update_statuses()
        result = run_all_scanners()
        self.stdout.write(
            self.style.SUCCESS(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 状态自动推进 {advanced} 条；"
                f"提醒生成 -> 待审批 {result['pending_approval']}、"
                f"待签到 {result['pending_sign_in']}、"
                f"待归还 {result['pending_return']}、"
                f"即将到期 {result['expiring']}、"
                f"已逾期 {result['overdue']}"
            )
        )
