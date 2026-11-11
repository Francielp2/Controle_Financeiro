from django import forms, template

register = template.Library()


@register.filter
def campo_tabler(campo):
    widget = campo.field.widget
    classes = widget.attrs.get("class", "").split()
    attrs = {}

    if isinstance(widget, forms.CheckboxInput):
        classes.append("form-check-input")
    elif isinstance(widget, forms.Select):
        classes.append("form-select")
    else:
        classes.append("form-control")

    if isinstance(widget, forms.Textarea):
        attrs["rows"] = 3

    if campo.errors:
        classes.append("is-invalid")

    attrs["class"] = " ".join(classes)
    html = campo.as_widget(attrs=attrs)
    if campo.field.show_hidden_initial:
        html += campo.as_hidden(only_initial=True)
    return html
