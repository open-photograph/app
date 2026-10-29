from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from ..services.contract import extract_variables, render_content


class TemplateVariableTests(SimpleTestCase):
    def render(self, content):
        return render_content(
            content, client=SimpleNamespace(name="Ana Silva", email="ana@example.com"), title="Ensaio"
        )

    def test_plain_placeholders_are_replaced(self):
        self.assertEqual(self.render("{{ cliente.nome }}: {{ contrato.titulo }}"), "Ana Silva: Ensaio")

    def test_saved_editor_autolinks_are_replaced_inside_placeholders(self):
        for protocol in ("http", "https"):
            content = "{{ [cliente.email](" + protocol + "://cliente.email) }}"
            self.assertEqual(self.render(content), r"ana@example\.com")
        self.assertEqual(self.render("{{[cliente.nome](http://cliente.nome/)}}"), "Ana Silva")

    def test_links_outside_placeholders_are_preserved(self):
        content = "[Site](https://example.com) {{ cliente.nome }}"
        self.assertEqual(self.render(content), "[Site](https://example.com) Ana Silva")

    def test_unknown_or_mismatching_autolinks_remain_invalid(self):
        for content in (
            "{{ desconhecida }}",
            "{{ [desconhecida](http://desconhecida) }}",
            "{{ [cliente.email](http://outro.example) }}",
        ):
            with self.assertRaises(ValidationError):
                self.render(content)

    def test_extracts_custom_variables_once_in_appearance_order(self):
        content = "{{name}} {{ valor }} {{name}} {{data_evento}}"
        self.assertEqual(extract_variables(content), ["name", "valor", "data_evento"])

    def test_renders_custom_variables_as_literal_text_without_recursive_expansion(self):
        content = "Nome: {{name}}. Valor: {{valor}}. Novamente: {{name}}"
        rendered = render_content(
            content,
            client=SimpleNamespace(name="Ana", email="ana@example.com"),
            title="Ensaio",
            variables={"name": "**Ana**", "valor": "{{outro}}"},
        )
        self.assertEqual(rendered, r"Nome: \*\*Ana\*\*. Valor: \{\{outro\}\}. Novamente: \*\*Ana\*\*")

    def test_missing_blank_and_extra_values_are_rejected(self):
        for values in ({}, {"name": "   "}, {"name": "Ana", "extra": "ignored"}):
            with self.assertRaises(ValidationError):
                render_content(
                    "{{name}}",
                    client=SimpleNamespace(name="Ana", email="ana@example.com"),
                    title="Ensaio",
                    variables=values,
                )
