"""Semantic colors shared by Qt styles and directly painted controls."""
LIGHT = dict(canvas='#f6f6f8', surface='#ffffff', raised='#eceef3',
             text='#202126', muted='#515460', accent='#0056b8',
             selected='#0056b8', selected_text='#ffffff', focus='#0056b8', pressed='#004895',
             border='#858b98', divider='#d9dde5', off_track='#737987',
             off_border='#737987', on_track='#16683d', on_border='#16683d',
             disabled_text='#626978', danger='#b42318', danger_bg='#fff0ee')
DARK = dict(canvas='#191a1e', surface='#25262b', raised='#303137',
            text='#f5f5f7', muted='#b2b5c0', accent='#a9ceff',
            selected='#c4ddff', selected_text='#172331', focus='#a9ceff', pressed='#476990',
            border='#8b919d', divider='#494b55', off_track='#737987',
            off_border='#8b919d', on_track='#16683d', on_border='#86deaf',
            disabled_text='#a4a8b2', danger='#ffada7', danger_bg='#482323')


def theme_colors(dark=False):
    return DARK if dark else LIGHT


def widget_colors(widget):
    window = widget.window()
    return getattr(window, 'confirmation_colors', theme_colors(bool(getattr(window, 'ui_dark', False))))
