from typing import List, Optional

class ActiveTimerViewModel:
    @property
    def timer_id(self) -> str: raise NotImplementedError
    @property
    def client_id(self) -> str: raise NotImplementedError
    @property
    def client_display_name(self) -> str: raise NotImplementedError
    @property
    def matter_id(self) -> str: raise NotImplementedError
    @property
    def matter_display_name(self) -> str: raise NotImplementedError
    @property
    def started_at(self) -> str: raise NotImplementedError
    @property
    def accumulated_elapsed_seconds(self) -> int: raise NotImplementedError
    @property
    def paused_at(self) -> Optional[str]: raise NotImplementedError
    @property
    def is_running(self) -> bool: raise NotImplementedError
    @property
    def is_paused(self) -> bool: raise NotImplementedError
    @property
    def description(self) -> str: raise NotImplementedError

class RecordedTimeEntryViewModel:
    @property
    def entry_id(self) -> str: raise NotImplementedError
    @property
    def recorded_date(self) -> str: raise NotImplementedError
    @property
    def decimal_hours(self) -> float: raise NotImplementedError
    @property
    def client_id(self) -> str: raise NotImplementedError
    @property
    def client_display_name(self) -> str: raise NotImplementedError
    @property
    def matter_id(self) -> str: raise NotImplementedError
    @property
    def matter_display_name(self) -> str: raise NotImplementedError
    @property
    def description(self) -> str: raise NotImplementedError
    @property
    def recorded_time(self) -> Optional[str]: raise NotImplementedError

class DailyTimeSummaryViewModel:
    @property
    def recorded_today_decimal(self) -> float: raise NotImplementedError
    @property
    def active_now_seconds(self) -> int: raise NotImplementedError
    @property
    def total_today_decimal(self) -> float: raise NotImplementedError

class TrayTimekeepingProvider:
    def get_active_timers(self) -> List[ActiveTimerViewModel]: raise NotImplementedError
    def get_recorded_entries_today(self) -> List[RecordedTimeEntryViewModel]: raise NotImplementedError
    def get_daily_summary(self) -> DailyTimeSummaryViewModel: raise NotImplementedError

class TrayCommandService:
    def start_timer(self) -> None: raise NotImplementedError
    def pause_timer(self, timer_id: str) -> None: raise NotImplementedError
    def resume_timer(self, timer_id: str) -> None: raise NotImplementedError
    def stop_timer(self, timer_id: str) -> None: raise NotImplementedError
    def open_cspm(self) -> None: raise NotImplementedError
    def open_time_dockets(self) -> None: raise NotImplementedError
    def open_reports(self) -> None: raise NotImplementedError
    def open_settings(self) -> None: raise NotImplementedError
    def exit_cspm(self) -> None: raise NotImplementedError
