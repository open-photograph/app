from rest_framework import serializers

from ..models import ContractTemplate
from ..services.contract import AUTOMATIC_VARIABLES, extract_variables


class ContractTemplateSerializer(serializers.ModelSerializer):
    variables = serializers.SerializerMethodField()
    input_variables = serializers.SerializerMethodField()
    content = serializers.CharField(max_length=200000)

    class Meta:
        model = ContractTemplate
        fields = ["id", "name", "content", "variables", "input_variables", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_variables(self, instance):
        return extract_variables(instance.content)

    def get_input_variables(self, instance):
        return [name for name in extract_variables(instance.content) if name not in AUTOMATIC_VARIABLES]
