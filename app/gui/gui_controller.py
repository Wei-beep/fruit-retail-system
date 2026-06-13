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
    ) -> None:
        self.transaction_flow = transaction_flow
        self.on_status = on_status
        self.on_transaction_ready = on_transaction_ready
        self.on_error = on_error
        self.on_cleared = on_cleared
        self.current_transaction: dict | None = None
        self._running = False

    def start_waiting(self) -> None:
        if self._running:
            return
        self._running = True
        self.current_transaction = None
        self.on_status("等待重量稳定...")
        thread = threading.Thread(target=self._prepare_in_background, daemon=True)
        thread.start()

    def _prepare_in_background(self) -> None:
        try:
            prepared = self.transaction_flow.prepare_transaction()
        except Exception as exc:
            self._running = False
            self.on_error(str(exc))
            return
        self.current_transaction = prepared
        self._running = False
        self.on_transaction_ready(prepared)

    def confirm_current(self) -> int | None:
        if not self.current_transaction:
            self.on_status("当前没有待确认交易")
            return None
        transaction_id = self.transaction_flow.confirm_transaction(self.current_transaction)
        self.current_transaction = None
        self.on_status(f"交易已确认，编号 {transaction_id}")
        self.on_cleared()
        self.start_waiting()
        return transaction_id

    def clear_current(self) -> None:
        self.current_transaction = None
        self.on_status("已清除当前待确认交易")
        self.on_cleared()
        self.start_waiting()
