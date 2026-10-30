from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name",
                  "is_staff", "is_active", "date_joined", "password"]
        read_only_fields = ["id", "date_joined", "is_staff", "is_active"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if self.instance is not None and request and request.user.is_staff:
            fields["is_active"].read_only = False
            fields["is_staff"].read_only = False
        return fields

    def validate(self, attrs):
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "A password is required."})
        if password is not None:
            user = User(**{key: attrs.get(key, getattr(self.instance, key, ""))
                           for key in ("username", "email", "first_name", "last_name")})
            try:
                validate_password(password, user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": exc.messages})
        request = self.context.get("request")
        if self.instance and request and self.instance.pk == request.user.pk:
            if attrs.get("is_active") is False or attrs.get("is_staff") is False:
                raise serializers.ValidationError("You cannot deactivate or demote your own account.")
        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user
