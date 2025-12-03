import dash
from dash import Dash, html, dcc, Input, Output

app = Dash(__name__, use_pages=True, suppress_callback_exceptions=True)

app.layout = html.Div([
    html.H1('Eearthquake Visualization Dashboard'),
    html.Div([
        html.Div(
            dcc.Link(f"{page['name']} - {page['path']}", href=page["relative_path"])
        ) for page in dash.page_registry.values()
    ]),
    dash.page_container
])

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
    app.run(debug=True)