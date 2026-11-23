from django import forms


class ConversationTitleForm(forms.Form):
    title = forms.CharField(max_length=70, min_length=1, strip=True)


class ShareExpirationForm(forms.Form):
    expiration_days = forms.IntegerField(min_value=1, max_value=30, initial=7)
