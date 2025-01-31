import sys

from django.apps import apps as django_apps
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.management.color import color_style
from django.db.models.deletion import ProtectedError
from django.db.utils import IntegrityError

style = color_style()


class PreloadDataError(Exception):
    pass


class PreloadData:

    def __init__(self, list_data=None, model_data=None, unique_field_data=None):
        self.list_data = list_data or {}
        self.model_data = model_data or {}
        self.unique_field_data = unique_field_data or {}
        self.load_list_data()
        self.load_model_data()
        self.update_unique_field_data()

    def load_list_data(self):
        """Loads data into a list model.

        List models have short_name, name where short_name is the unique field.

        Format:
            {model_name1: [(short_name1, name), (short_name2, name),...],
             model_name1: [(short_name1, name), (short_name2, name),...],
            ...}
        """
        for model_name in self.list_data.keys():
            try:
                model = django_apps.get_model(model_name)
                for data in self.list_data.get(model_name):
                    short_name, display_value = data
                    try:
                        obj = model.objects.get(short_name=short_name)
                    except ObjectDoesNotExist:
                        model.objects.create(
                            short_name=short_name, name=display_value)
                    else:
                        obj.name = display_value
                        obj.save()
            except Exception as e:
                raise PreloadDataError(e)
                # sys.stdout.write(style.ERROR(str(e) + '\n'))

    def load_model_data(self):
        """Loads data into a model, creates or updates existing.

        Must have a unique field

        Format:
            {app_label.model1: [{field_name1: value, field_name2: value ...},...],
             (app_label.model2, unique_field_name): [{field_name1: value,
             unique_field_name: value ...}, ...],
             ...}
        """
        for model_name, datas in self.model_data.items():
            try:
                model_name, unique_field = model_name
            except ValueError:
                unique_field = None
            model = django_apps.get_model(model_name)
            unique_field = unique_field or self.guess_unique_field(model)
            for data in datas:
                try:
                    obj = model.objects.get(
                        **{unique_field: data.get(unique_field)})
                except ObjectDoesNotExist:
                    try:
                        model.objects.create(**data)
                    except IntegrityError:
                        pass
                else:
                    for key, value in data.items():
                        setattr(obj, key, value)
                    obj.save()

    def update_unique_field_data(self):  # noqa
        """Updates the values of the unique fields in a model.

        Model must have a unique field and the record must exist

        Format:
            {model_name1: {unique_field_name: (current_value, new_value)},
             model_name2: {unique_field_name: (current_value, new_value)},
             ...}
        """
        for model_name, data in self.unique_field_data.items():
            model = django_apps.get_model(*model_name.split('.'))
            for field, values in data.items():
                try:
                    obj = model.objects.get(**{field: values[1]})
                except model.DoesNotExist as e:  # noqa
                    try:
                        obj = model.objects.get(**{field: values[0]})
                    except model.DoesNotExist as e:
                        sys.stdout.write(style.ERROR(str(e) + '\n'))
                    except MultipleObjectsReturned as e:
                        sys.stdout.write(style.ERROR(str(e) + '\n'))
                    else:
                        setattr(obj, field, values[1])
                        obj.save()
                else:
                    try:
                        obj = model.objects.get(**{field: values[0]})
                    except model.DoesNotExist as e:  # noqa
                        pass
                    else:
                        try:
                            obj.delete()
                        except ProtectedError:
                            pass

    def guess_unique_field(self, model):
        """Returns the first field name for a unique field.
        """
        unique_field = None
        for field in model._meta.get_fields():
            try:
                if field.unique and field.name != 'id':
                    unique_field = field.name
                    break
            except AttributeError:
                pass
        return unique_field
