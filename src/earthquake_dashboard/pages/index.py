import dash
from dash import dcc, html

dash.register_page(__name__, path = '/')

layout = html.Div([
    html.Div([
        html.H1('Earthquake Visualization Dashboard',
                style={'textAlign': 'center', 'color': 'rgb(148, 148, 239)', 'marginBottom': '10px'}),

        html.P('An interactive dashboard for visualizing earthquake data from the USGS Earthquake Catalog API',
               style={'textAlign': 'center', 'fontSize': '18px', 'color': 'rgb(108, 108, 224)', 'marginBottom': '30px'}),

        html.Hr(style={'borderColor': 'rgb(0,70,139)'}),

        html.H2('Quick Start Guide', style={'color': 'rgb(148, 148, 239)', 'marginTop': '20px'}),

        html.Div([
            html.H3('1. Data Loading', style={'color': 'rgb(108, 108, 224)'}),
            html.P([
                'The dashboard uses the ',
                html.Code('DataLoader', style={
                    'backgroundColor': 'rgb(0,0,114)',
                    'color': 'rgb(148, 148, 239)',
                    'padding': '2px 6px',
                    'borderRadius': '3px',
                    'fontFamily': 'monospace'
                }),
                ' class to fetch earthquake data from the USGS API. To customize your data query:'
            ]),
            html.Ul([
                html.Li('Modify parameters in DataLoader.py (date range, magnitude, location, depth)'),
                html.Li('Maximum 20,000 records per query'),
                html.Li('Default date range: Past 7 days'),
                html.Li('Default minimum magnitude: 6.0'),
            ]),

            html.H3('2. Visualization Features', style={'color': 'rgb(108, 108, 224)', 'marginTop': '20px'}),
            html.P('The dashboard provides multiple interactive visualization options:'),

            html.H4('Map Projection Controls:', style={'color': 'rgb(148, 148, 239)', 'marginLeft': '20px'}),
            html.Ul([
                html.Li([html.Strong('Projection Type:'), ' Choose between equalEarth, mercator, or azimuthalEqualArea projections']),
                html.Li([html.Strong('Rotation (Phi/Theta):'), ' Rotate the globe to view different perspectives']),
                html.Li([html.Strong('Scale:'), ' Zoom in/out on the map (10-1000)']),
            ], style={'marginLeft': '20px'}),

            html.H4('Visual Encodings:', style={'color': 'rgb(148, 148, 239)', 'marginLeft': '20px'}),
            html.Ul([
                html.Li([html.Strong('Size Variable:'), ' Control point size based on magnitude, significance, or other metrics']),
                html.Li([html.Strong('Color Variable:'), ' Color points by magnitude, depth, time, or significance']),
                html.Li([html.Strong('Opacity Variable:'), ' Adjust transparency based on selected metric']),
            ], style={'marginLeft': '20px'}),

            html.H4('Styling Options:', style={'color': 'rgb(148, 148, 239)', 'marginLeft': '20px'}),
            html.Ul([
                html.Li([html.Strong('Map Fill Color:'), ' Customize land mass color (e.g., #4287f5)']),
                html.Li([html.Strong('Map Stroke Color:'), ' Set border color for countries']),
                html.Li([html.Strong('Background Color:'), ' Change the visualization background']),
            ], style={'marginLeft': '20px'}),

            html.H3('3. Interactive Filtering', style={'color': 'rgb(108, 108, 224)', 'marginTop': '20px'}),
            html.P('Filter earthquake data using multiple methods:'),
            html.Ul([
                html.Li([html.Strong('Histogram Brushes:'), ' Click and drag on any histogram to filter by that dimension']),
                html.Li([html.Strong('Map Selection:'), ' Click and drag on the map to select earthquakes by location']),
                html.Li([html.Strong('Multiple Filters:'), ' Select which dimensions to display as filter histograms']),
                html.Li([html.Strong('Linked Views:'), ' All visualizations update together based on your selections']),
            ]),

            html.H3('4. Heatmap Analysis', style={'color': 'rgb(108, 108, 224)', 'marginTop': '20px'}),
            html.P('Explore relationships between variables using the heatmap:'),
            html.Ul([
                html.Li('Choose X-axis variable (default: time)'),
                html.Li('Choose Y-axis variable (default: depth)'),
                html.Li('Color shows maximum magnitude in each bin'),
                html.Li('Hover over cells to see detailed statistics'),
            ]),

            html.H3('5. Available Data Fields', style={'color': 'rgb(108, 108, 224)', 'marginTop': '20px'}),
            html.Ul([
                html.Li([html.Strong('place:'), ' Location description']),
                html.Li([html.Strong('time:'), ' When the earthquake occurred']),
                html.Li([html.Strong('lat/lon:'), ' Geographic coordinates']),
                html.Li([html.Strong('mag:'), ' Magnitude (Richter scale)']),
                html.Li([html.Strong('sig:'), ' Significance score']),
                html.Li([html.Strong('depth:'), ' Depth in kilometers']),
                html.Li([html.Strong('tsunami:'), ' Whether a tsunami was generated']),
                html.Li([html.Strong('cdi:'), ' Community Decimal Intensity']),
                html.Li([html.Strong('alert:'), ' Alert level (green, yellow, orange, red)']),
            ]),

            html.H3('6. Tips for Best Experience', style={'color': 'rgb(108, 108, 224)', 'marginTop': '20px'}),
            html.Ul([
                html.Li('Start with broad filters, then narrow down using histogram brushes'),
                html.Li('Try different projections to see spatial patterns more clearly'),
                html.Li('Use the heatmap to identify temporal patterns and depth relationships'),
                html.Li('Hover over earthquake points to see detailed information'),
                html.Li('Clear selections by clicking outside the brushed area'),
            ]),

            html.Hr(style={'marginTop': '30px', 'borderColor': 'rgb(0,70,139)'}),

            html.Div([
                html.H3('Ready to Explore?', style={'color': 'rgb(148, 148, 239)', 'textAlign': 'center'}),
                dcc.Link(
                    html.Button('Launch Dashboard',
                               style={
                                   'fontSize': '20px',
                                   'padding': '15px 40px',
                                   'backgroundColor': 'rgb(0,70,139)',
                                   'color': 'rgb(148, 148, 239)',
                                   'border': '2px solid rgb(108, 108, 224)',
                                   'borderRadius': '5px',
                                   'cursor': 'pointer',
                                   'display': 'block',
                                   'margin': '0 auto',
                                   'fontFamily': 'monospace',
                                   'fontWeight': 'bold'
                               }),
                    href='/dashboard'
                ),
            ], style={'textAlign': 'center', 'marginTop': '20px', 'marginBottom': '40px'}),

            html.Hr(style={'borderColor': 'rgb(0,70,139)'}),

            html.Div([
                html.P([
                    'Data Source: ',
                    html.A('USGS Earthquake Catalog API',
                          href='https://earthquake.usgs.gov/fdsnws/event/1/',
                          target='_blank',
                          style={'color': 'rgb(108, 108, 224)', 'textDecoration': 'underline'})
                ], style={'textAlign': 'center', 'color': 'rgb(148, 148, 239)', 'fontSize': '14px'}),
            ]),

        ], style={
            'maxWidth': '900px',
            'margin': '0 auto',
            'padding': '20px',
            'backgroundColor': 'rgb(0,0,88)',
            'borderRadius': '10px',
            'fontFamily': 'monospace',
            'border': '2px solid rgb(0,70,139)'
        })
    ], style={
        'padding': '40px 20px',
        'backgroundColor': 'rgb(0,0,63)',
        'minHeight': '100vh',
        'color': 'rgb(148, 148, 239)'
    })
])