"""Structured system notifications: translate wording, preserve user values."""
from dataclasses import dataclass, field
from django.utils.functional import Promise
from django.utils.translation import gettext, override


def _encode(value):
    if isinstance(value, SystemMessage):
        return {'kind': 'message', 'source': value.source, 'parameters': value.parameters}
    if isinstance(value, Promise):
        with override('en'):
            return {'kind': 'label', 'value': str(value)}
    return value if isinstance(value, (int, float, bool)) or value is None else str(value)


def _decode(value):
    if isinstance(value, dict) and value.get('kind') == 'message':
        return render_message(value['source'], value['parameters'])
    if isinstance(value, dict) and value.get('kind') == 'label':
        return gettext(value['value'])
    return value


def render_message(source, parameters):
    return gettext(source) % {key: _decode(value) for key, value in parameters.items()} if parameters else gettext(source)


@dataclass(frozen=True)
class SystemMessage:
    source: str
    parameters: dict = field(default_factory=dict)

    def english(self):
        with override('en'):
            return render_message(self.source, self.parameters)


def message(source, **parameters):
    return SystemMessage(source, {key: _encode(value) for key, value in parameters.items()})
