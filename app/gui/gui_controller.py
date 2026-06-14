from __future__ import annotations

import threading
from typing import Callable

from app.workflow.transaction_flow import TransactionFlow


class GUIController:
    def __init__(
        self,
        transaction_flow: TransactionFlow,
        on_status: Callable[[str], None],
        on_transaction_ready: Callable[[dict], None],
        on_error: Callable[[str], None],
        on_cleared: Callable[[], None],
        on_reading: Callable[[float, bool], None] | None = None,
        include_candidates: bool = False,
        auto_restart_after_confirm: bool = True,
    ) -> None:
        self.transaction_flow = transaction_flow
        self.on_status = on_status
        self.on_transaction_ready = on_transaction_ready
        self.on_error = on_error
        self.on_cleared = on_cleared
        # 以下三项默认值保持原 Tk 行为不变；Web 前端按需开启
        self.on_reading = on_reading
        self.include_candidates = include_candidates
        self.auto_restart_after_confirm = auto_restart_after_confirm
        self.current_transaction: dict | None = None
        self._running = False
        self._stopped = False

    def stop(self) -> None:
        """退出时调用：阻止后续后台准备循环继续排队。"""
        self._stopped = True
        self._running = False

    def start_waiting(self) -> None:
        if self._stopped or self._running:
            return
        self._running = True
        self.current_transaction = None
        self.on_status("等待重量稳定...")
        thread = threading.Thread(target=self._prepare_in_background, daemon=True)
        thread.start()

    def _prepare_in_background(self) -> None:
        try:
            prepared = self.transaction_flow.prepare_transaction(
                include_candidates=self.include_candidates,
                on_reading=self.on_reading,
            )
        except Exception as exc:
            self._running = False
            self.on_error(str(exc))
            return
        self.current_transaction = prepared
        self._running = False
        self.on_transaction_ready(prepared)

    def select_label(self, label: str) -> None:
        """手动改判：按所选商品 label 沿用已存重量重新计价并回灌界面。"""
        if not self.current_transaction:
            self.on_status("当前没有待确认交易")
            return
        try:
            product = self.transaction_flow.price_service.get_price(label)
        except Exception as exc:
            self.on_error(str(exc))
            return
        weight_kg = self.current_transaction["weight_kg"]
        total_price = self.transaction_flow.transaction_service.calculate_total(
            weight_kg, product["price_per_kg"]
        )
        updated = dict(self.current_transaction)
        updated.update(
            {
                "label": product["label"],
                "name_cn": product["name_cn"],
                "price_per_kg": product["price_per_kg"],
                "total_price": total_price,
                "low_confidence": False,
            }
        )
        self.current_transaction = updated
        self.on_transaction_ready(updated)

    def confirm_current(self) -> int | None:
        if not self.current_transaction:
            self.on_status("当前没有待确认交易")
            return None
        # 低置信且尚未手动选品时 total 为空，不允许确认
        if self.current_transaction.get("total_price") is None:
            self.on_status("请先选择商品种类")
            return None
        transaction_id = self.transaction_flow.confirm_transaction(self.current_transaction)
        self.current_transaction = None
        self.on_status(f"交易已确认，编号 {transaction_id}")
        # Tk：确认后清空并自动进入下一轮等待。
        # Web：auto_restart=False，确认后展示支付引导，回到等待由前端"完成"(clear)触发。
        if self.auto_restart_after_confirm:
            self.on_cleared()
            self.start_waiting()
        return transaction_id

    def clear_current(self) -> None:
        self.current_transaction = None
        self.on_status("已清除当前待确认交易")
        self.on_cleared()
        self.start_waiting()
