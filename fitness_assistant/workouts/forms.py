from django import forms

class SplitDaysForm(forms.Form):
    """Step 1: the user manually types how many days/week they train."""
    days_per_week = forms.IntegerField(
        min_value=1,
        max_value=7,
        label='Training days per week',
        widget=forms.NumberInput(attrs={'min': '1', 'max': '7', 'placeholder': 'e.g. 5'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': (
                    'mt-1 block w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl '
                    'text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 '
                    'focus:border-blue-500 transition duration-150 ease-in-out sm:text-sm'
                )
            })
