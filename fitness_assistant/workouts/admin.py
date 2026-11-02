from django.contrib import admin
from .models import (
    WorkoutLog, WorkoutSplit, SplitDay, SplitExercise,
    Exercise, WorkoutSession, SessionExercise, SessionSet,
)

class WorkoutLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'exercise', 'sets', 'reps', 'weight_kg', 'volume', 'date']
    list_filter = ['exercise', 'date', 'user']
    search_fields = ['user__email', 'exercise']
    readonly_fields = ['volume']

admin.site.register(WorkoutLog, WorkoutLogAdmin)


class SplitExerciseInline(admin.TabularInline):
    model = SplitExercise
    extra = 0

class SplitDayInline(admin.TabularInline):
    model = SplitDay
    extra = 0

class WorkoutSplitAdmin(admin.ModelAdmin):
    list_display = ['user', 'days_per_week', 'updated_at']
    search_fields = ['user__email']
    inlines = [SplitDayInline]

class SplitDayAdmin(admin.ModelAdmin):
    list_display = ['split', 'order', 'label', 'muscle_focus']
    inlines = [SplitExerciseInline]

admin.site.register(WorkoutSplit, WorkoutSplitAdmin)
admin.site.register(SplitDay, SplitDayAdmin)


class ExerciseAdmin(admin.ModelAdmin):
    list_display = ['name', 'muscle_group', 'user']
    list_filter = ['muscle_group']
    search_fields = ['name', 'user__email']

admin.site.register(Exercise, ExerciseAdmin)


class SessionSetInline(admin.TabularInline):
    model = SessionSet
    extra = 0

class SessionExerciseAdmin(admin.ModelAdmin):
    list_display = ['name', 'session', 'muscle_group', 'rest_sec']
    inlines = [SessionSetInline]

class SessionExerciseInline(admin.TabularInline):
    model = SessionExercise
    extra = 0
    show_change_link = True

class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'day_label', 'duration_min', 'calories']
    list_filter = ['date', 'user']
    search_fields = ['user__email', 'day_label']
    inlines = [SessionExerciseInline]

admin.site.register(WorkoutSession, WorkoutSessionAdmin)
admin.site.register(SessionExercise, SessionExerciseAdmin)
