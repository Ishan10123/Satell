from django import forms

MAX_MESSAGE_CHARS = 5000


class MessageForm(forms.Form):
    content = forms.CharField(min_length=1, max_length=MAX_MESSAGE_CHARS, strip=True, widget=forms.Textarea)
