from django.contrib import admin

from .models import ChatMessage, ChatThread, Evaluation, Reservation, ReservationStatusLog


class ReservationStatusLogInline(admin.TabularInline):
    model = ReservationStatusLog
    extra = 0
    readonly_fields = ("from_status", "to_status", "action", "operator_name", "remark", "created_at")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("no", "applicant_name", "laboratory", "device", "start_time",
                    "end_time", "status", "urgency", "is_evaluated")
    list_filter = ("status", "urgency", "laboratory", "is_evaluated")
    search_fields = ("no", "applicant_name", "device__name", "device__code")
    date_hierarchy = "start_time"
    inlines = [ReservationStatusLogInline]


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "reservation", "status", "message_count", "last_message_time")
    list_filter = ("status",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender_name", "is_admin_side", "content", "created_at")
    list_filter = ("is_admin_side",)


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("id", "reservation", "evaluator_name", "device_score", "speed_score",
                    "service_score", "average_score", "created_at")
    search_fields = ("reservation__no", "evaluator_name", "content")
