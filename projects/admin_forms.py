"""فرم‌های سفارشی پنل مدیریت برای نمایش دوستانه‌ی فیلدهای GenericForeignKey.

به‌جای دو فیلد فنی «نوع موجودیت» و «شناسه‌ی عددی»، یک منوی کشویی واحد با نام‌های
واقعی افراد نمایش داده می‌شود.
"""

from django import forms
from django.contrib.contenttypes.models import ContentType


def _encode(content_type, object_id):
    return f"{content_type.pk}:{object_id}"


def _decode(value):
    ct_id, obj_id = value.split(":")
    return ContentType.objects.get(pk=ct_id), int(obj_id)


def _build_choices(models_and_labels):
    choices = [("", "--- انتخاب کنید ---")]
    for model, label in models_and_labels:
        ct = ContentType.objects.get_for_model(model)
        for obj in model.objects.all().order_by("full_name"):
            choices.append((_encode(ct, obj.pk), f"{label}: {obj.full_name}"))
    return choices


class GenericChoiceFormMixin:
    """کلاس پایه برای فرم‌هایی که یک زوج (content_type, object_id) دارند.

    فرم فرزند باید فیلد ``generic_field_name`` را به‌صورت یک ``forms.ChoiceField``
    در سطح کلاس تعریف کند (تا در ``base_fields`` دیده شود و بررسی‌های ادمین جنگو
    آن را معتبر بشناسند)؛ این کلاس فقط گزینه‌ها و مقدار اولیه را در زمان اجرا پر
    می‌کند، چون فهرست افراد باید همیشه تازه باشد.
    """

    generic_field_name = None  # نام فیلد نمایشی، مثلاً "executor_choice"
    generic_ct_field = None  # نام واقعی فیلد content type روی مدل
    generic_id_field = None  # نام واقعی فیلد object id روی مدل
    generic_models_and_labels = ()  # (( مدل، برچسب), ...)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.generic_field_name].choices = _build_choices(self.generic_models_and_labels)

        instance = getattr(self, "instance", None)
        ct = getattr(instance, f"{self.generic_ct_field}_id", None) if instance else None
        obj_id = getattr(instance, self.generic_id_field, None) if instance else None
        if ct and obj_id:
            self.initial[self.generic_field_name] = _encode(ContentType.objects.get(pk=ct), obj_id)

    def _post_clean(self):
        """پیش از فراخوانی instance.full_clean() توسط ModelForm، مقدار GFK را
        از منوی کشویی روی instance می‌گذاریم تا clean() سفارشی مدل به مشکل
        نخورد (چون این دو فیلد از فرم exclude شده‌اند)."""
        value = self.cleaned_data.get(self.generic_field_name)
        if value:
            content_type, object_id = _decode(value)
            setattr(self.instance, self.generic_ct_field, content_type)
            setattr(self.instance, self.generic_id_field, object_id)
        else:
            setattr(self.instance, f"{self.generic_ct_field}_id", None)
            setattr(self.instance, self.generic_id_field, None)
        super()._post_clean()
