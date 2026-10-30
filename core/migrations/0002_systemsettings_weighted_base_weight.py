import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.AddField(
        model_name="systemsettings", name="weighted_base_weight",
        field=models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)]),
    )]
