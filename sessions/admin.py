from django.contrib import admin

from sessions.models import LunchSession, SelectionResult, SessionProposal, Suggestion, Vote


class SessionProposalInline(admin.TabularInline):
    model = SessionProposal
    extra = 0
    filter_horizontal = ["menu_items"]


class VoteInline(admin.TabularInline):
    model = Vote
    extra = 0


@admin.register(LunchSession)
class LunchSessionAdmin(admin.ModelAdmin):
    list_display = ["title", "team", "start_time", "end_time", "selection_algorithm", "created_by"]
    list_filter = ["selection_algorithm", "is_recurring", "team"]
    search_fields = ["title"]
    inlines = [SessionProposalInline]


@admin.register(SessionProposal)
class SessionProposalAdmin(admin.ModelAdmin):
    list_display = ["session", "restaurant", "proposer", "created_at"]
    search_fields = ["restaurant__name"]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ["voter", "proposal", "choice", "voted_at"]
    list_filter = ["choice"]


@admin.register(SelectionResult)
class SelectionResultAdmin(admin.ModelAdmin):
    list_display = ["session", "selected_proposal", "method_used", "executed_at"]
    list_filter = ["method_used"]


@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    list_display = ["user", "restaurant", "session", "status", "created_at"]
    list_filter = ["status", "session"]
    search_fields = ["user__username", "restaurant__name"]
