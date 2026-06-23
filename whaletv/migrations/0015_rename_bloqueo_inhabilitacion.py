from django.db import migrations


class Migration(migrations.Migration):
    """Renombra el vocabulario bloquear/desbloquear → inhabilitar/habilitar.

    Solo renombra modelo y campos (preserva todos los datos). Los cambios de
    verbose_name / Meta van en la migración siguiente.
    """

    dependencies = [
        ('whaletv', '0014_syncjob_tipo_syncjobitem_coincide_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Bloqueo',
            new_name='Inhabilitacion',
        ),
        migrations.RenameField(
            model_name='televisor',
            old_name='lock_status',
            new_name='inhabilitado',
        ),
        migrations.RenameField(
            model_name='registrosync',
            old_name='lock_status',
            new_name='inhabilitado',
        ),
        migrations.RenameField(
            model_name='syncjobitem',
            old_name='remoto_bloqueado',
            new_name='remoto_inhabilitado',
        ),
        migrations.RenameField(
            model_name='syncjobitem',
            old_name='local_bloqueado',
            new_name='local_inhabilitado',
        ),
    ]
