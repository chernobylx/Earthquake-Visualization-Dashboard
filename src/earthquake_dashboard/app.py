import os

import dash
from dash import Dash, Input, Output, State, callback, dcc, html

# JetBrains Mono carries the whole redesign: every size, weight and letter-space
# in assets/styles.css is picked against it. The stack falls back to the browser's
# own monospace, so the layout survives the font failing to load.
FONTS = [
    'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap',
]

app = Dash(__name__, use_pages=True, suppress_callback_exceptions=True,
           external_stylesheets=FONTS,
           title='USGS Earthquake Explorer')

# Page order in the header follows the registry's own order, which is path order:
# '/' (Quick start) then '/dashboard'.
NAV = [('Quick start', '/'), ('Dashboard', '/dashboard')]


def build_header():
    return html.Header([
        html.Div([
            html.Div([
                html.Span(className='brand-dot'),
                html.Span('USGS Earthquake Explorer', className='brand-name'),
            ], className='brand'),
            html.Nav([
                dcc.Link(label, href=href, className='nav-link', id=f'nav-{href.strip("/") or "home"}')
                for label, href in NAV
            ], className='nav'),
            html.Div([
                html.Span([html.Span(className='live-dot'), 'catalog live'], className='status-live'),
                html.Span(id='header_range', className='status-range'),
                html.Span(id='header_count', className='status-count'),
            ], className='status'),
        ], className='header-inner'),
    ], className='site-header')


app.layout = html.Div([
    # Sits behind everything at z-index 0; assets/backdrop.js animates it and
    # honours prefers-reduced-motion. Purely decorative, hence aria-hidden.
    html.Canvas(id='backdrop', className='backdrop', **{'aria-hidden': 'true'}),
    build_header(),
    html.Main(dash.page_container, className='page'),
], id='layout')


@callback(
    Output('header_range', 'children'),
    Output('header_count', 'children'),
    Input('count_output', 'children'),
    Input('data_table', 'data'),
    State('date_range_picker', 'start_date'),
    State('date_range_picker', 'end_date'),
)
def mirror_status(count_children, rows, start_date, end_date):
    """Echo the query's date span and event count into the header.

    Rows actually downloaded beat a preview count, so a fetch without a preview
    still reads as loaded rather than "no query yet". Driven off the two outputs
    rather than the buttons so the header follows whatever the page already
    decided to show, including its initial prompt.
    """
    span = '—'
    if start_date and end_date:
        span = f'{str(start_date)[:10]} → {str(end_date)[:10]}'

    if rows:
        return span, [html.Span(f'{len(rows):,}', className='count-n'), ' loaded']

    # count_output is [H5('Matching Events'), <text>]; the text is a bare string
    # before a query has run and a formatted count afterwards.
    text = ''
    if isinstance(count_children, list):
        tail = [c for c in count_children if isinstance(c, str)]
        text = tail[-1] if tail else ''
    elif isinstance(count_children, str):
        text = count_children

    digits = ''.join(c for c in text if c.isdigit() or c == ',')
    events = [html.Span(digits, className='count-n'), ' matching'] if digits else 'no query yet'
    return span, events


# Clientside callback to capture visualizer_output div dimensions
app.clientside_callback(
    """
    function(n_clicks) {
        // Only execute if button was clicked
        if (!n_clicks || n_clicks === 0) {
            return window.dash_clientside.no_update;
        }

        // Get the visualizer_output div
        const vizDiv = document.getElementById('visualizer_output');

        if (!vizDiv) {
            console.error('visualizer_output div not found');
            return {width: null, height: null};
        }

        // Get computed dimensions
        const rect = vizDiv.getBoundingClientRect();
        const width = Math.floor(rect.width);
        const height = Math.floor(rect.height);

        console.log('Captured dimensions:', width, height);

        return {width: width, height: height};
    }
    """,
    Output('visualizer_dimensions', 'data'),
    Input('viz_button', 'n_clicks')
)

if __name__ == '__main__':
    app.run(debug=os.environ.get('DASH_DEBUG', '').lower() in ('1', 'true'))
