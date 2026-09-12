"""Quick start — implements the guide route of the redesign.

The content is the same ground the old page covered; what changed is the shape.
The redesign turns six numbered steps into a ruled grid and the reference
material into four short key/value groups, so the page reads as a card you scan
rather than a page you read top to bottom.
"""

import dash
from dash import dcc, html

dash.register_page(__name__, path='/', name='Quick start')

STEPS = [
    ('01', 'Set the query',
     'Date, magnitude, significance, depth and a lat/lon box. Defaults cover the past 30 days.'),
    ('02', 'Preview count',
     'Asks USGS how many events match and downloads nothing.'),
    ('03', 'Fetch data',
     'Pulls the matching records into the table, up to 20,000 per request.'),
    ('04', 'Filter the table',
     'Sort or type into the table’s filter row — the chart reads the narrowed frame, '
     'not the full download.'),
    ('05', 'Render chart',
     'Builds the linked map, histograms and heatmap from whatever the table currently holds.'),
    ('06', 'Explore data',
     'Brush the map, a histogram or the heatmap — every other view cross-filters to the '
     'same selection.'),
]

GROUPS = [
    ('Map controls', [
        ('Projection', 'Natural Earth, azimuthal equal-area or Mercator'),
        ('Spin / Tilt', 'Rotate the globe east–west and north–south'),
        ('Zoom', 'Scales the geography from 10 to 1000'),
    ]),
    ('Encodings', [
        ('Point size', 'Any numeric column, scaled by area'),
        ('Point colour', 'Magnitude, depth, time or significance'),
        ('Point opacity', 'Fades points by the metric you choose'),
    ]),
    ('Filtering', [
        ('Brush', 'Drag any histogram to filter every other view'),
        ('Map select', 'Drag across the globe to filter by location'),
        ('Clear', 'Click outside a brushed area to release it'),
    ]),
    ('Fields', [
        ('mag / sig', 'Magnitude and USGS significance score'),
        ('depth', 'Kilometres below sea level; negatives sit above'),
        ('cdi / alert', 'Reported shaking and PAGER alert level'),
    ]),
]

layout = html.Div([
    html.P('Quick start', className='guide-eyebrow'),
    html.H1('Query the USGS catalog, then brush it from any angle.'),
    html.P('Every view shares one set of Vega-Lite selections, so a brush drawn in the map, '
           'a histogram, or the heatmap filters all the others. Capped at 20,000 records '
           'per request.', className='guide-lede'),

    html.Div([
        html.Div([
            html.Div(n, className='step-n'),
            html.Div(title, className='step-title'),
            html.Div(body, className='step-body'),
        ], className='step') for n, title, body in STEPS
    ], className='steps'),

    html.Div([
        html.Div([
            html.H3(title),
            *[html.Div([
                html.Span(k, className='guide-k'),
                html.Span(v, className='guide-v'),
            ], className='guide-row') for k, v in items],
        ]) for title, items in GROUPS
    ], className='guide-groups'),

    html.Div([
        dcc.Link(html.Button('Launch dashboard →', className='cta'), href='/dashboard'),
        html.Span(['data source · ',
                   html.A('USGS FDSN event API',
                          href='https://earthquake.usgs.gov/fdsnws/event/1/',
                          target='_blank')], className='guide-source'),
    ], className='guide-foot'),
], className='guide')
