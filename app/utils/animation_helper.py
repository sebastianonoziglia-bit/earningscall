"""
Helper utilities for consistent animations across charts
"""
import plotly.graph_objects as go

def get_animation_controls(frames_duration=500, transition_duration=300):
    """
    Create animation control buttons with consistent style
    
    Args:
        frames_duration: Duration of each frame in milliseconds
        transition_duration: Duration of the transition between frames
        
    Returns:
        List of animation control configurations
    """
    return [{
        'buttons': [
            {
                'args': [None, {
                    'frame': {'duration': frames_duration, 'redraw': True},
                    'fromcurrent': True,
                    'transition': {'duration': transition_duration, 'easing': 'cubic-in-out'}
                }],
                'label': 'Play',
                'method': 'animate'
            },
            {
                'args': [[None], {
                    'frame': {'duration': 0, 'redraw': False},
                    'mode': 'immediate',
                    'transition': {'duration': 0}
                }],
                'label': 'Pause',
                'method': 'animate'
            }
        ],
        'direction': 'left',
        'pad': {'r': 10, 't': 87},
        'showactive': False,
        'type': 'buttons',
        'x': 0.1,
        'xanchor': 'right',
        'y': 0,
        'yanchor': 'top'
    }]

def create_animation_buttons(x_position=0.5, y_position=1.18):
    """
    Create standardized animation buttons with consistent settings
    
    Args:
        x_position: Horizontal position (0-1)
        y_position: Vertical position (relative to figure)
    
    Returns:
        List of animation button configurations
    """
    return [{
        'type': 'buttons',
        'buttons': [
            {
                'label': '▶',
                'method': 'animate',
                'args': [None, {
                    'frame': {'duration': 500, 'redraw': True},  # keep scaling consistent across frames
                    'fromcurrent': True,
                    'transition': {'duration': 300, 'easing': 'cubic-in-out'}
                }]
            },
            {
                'label': '❚❚',
                'method': 'animate',
                'args': [[None], {
                    'frame': {'duration': 0, 'redraw': False},  # Set redraw to False for better pausing
                    'mode': 'immediate',
                    'transition': {'duration': 0}
                }]
            }
        ],
        'direction': 'left',
        'showactive': False,
        'x': x_position,
        'y': y_position,
        'xanchor': 'left',
        'yanchor': 'top',
        'pad': {'t': 2, 'r': 6, 'l': 0, 'b': 0},
        'bgcolor': 'rgba(15, 23, 42, 0.55)',
        'bordercolor': 'rgba(255, 255, 255, 0.22)',
        'borderwidth': 1,
        'font': {'size': 14, 'color': '#F8FAFC'}
    }]

def create_year_annotation(year, size=24, x=0.5, y=0.5):
    """
    Create standardized year annotation
    
    Args:
        year: Year to display
        size: Font size
        
    Returns:
        List of annotation configurations
    """
    return [{
        'text': f'<b>Year: {year}</b>',
        'x': x,
        'y': y,
        'xref': 'paper',
        'yref': 'paper',
        'showarrow': False,
        'font': {
            'size': size,
            'color': 'rgba(15, 23, 42, 0.35)',
            'family': 'system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif'
        }
    }]

def update_chart_layout(
    fig,
    title,
    x_title,
    max_value,
    tick_vals,
    tick_text,
    year,
    height=500,
    use_default_annotation=False,
    show_animation_buttons=True,
):
    """
    Apply consistent layout settings to a chart
    
    Args:
        fig: Plotly figure object
        title: Chart title
        x_title: X-axis title
        max_value: Maximum value for consistent x-axis scaling
        tick_vals: X-axis tick values
        tick_text: X-axis tick labels
        year: Current year for annotation
        height: Chart height
        use_default_annotation: If True, create a year annotation; if False, assume existing annotations
        
    Returns:
        Updated figure
    """
    # Create animation buttons (subtle, next to title)
    buttons = create_animation_buttons(x_position=0.01, y_position=1.16) if show_animation_buttons else []
    
    # Determine the available years for this chart
    years = []
    if hasattr(fig, "frames") and fig.frames:
        years = sorted([int(frame.name) for frame in fig.frames if frame.name.isdigit()])
    
    # Create a title that shows the year range for animation
    if years:
        year_range = f" (Animation: {min(years)}-{max(years)})"
        full_title = f"{title}{year_range}"
    else:
        full_title = title
    
    # Update layout with consistent settings
    # Add headroom so outside labels never collide with the bar end or the plot edge,
    # but keep it tight so bars use most of the available width.
    padded_max_value = max_value * 1.10 if max_value else max_value
    layout_update = {
        'height': height,
        'showlegend': False,
        'plot_bgcolor': 'rgba(0,0,0,0)',
        'paper_bgcolor': 'rgba(0,0,0,0)',
        # Disable drag interactions (prevents left/right panning/dragging).
        'dragmode': False,
        'font': {
            'family': 'system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif',
            'color': '#0f172a'
        },
        'xaxis': dict(
            title=x_title,
            showgrid=False,
            zeroline=False,
            showline=False,
            tickmode='array',
            tickvals=tick_vals,
            ticktext=tick_text,
            # Set fixed range for consistent scaling during animation (+ padding for outside labels)
            range=[0, padded_max_value],
            fixedrange=True,
        ),
        'yaxis': dict(
            title="",
            tickangle=0,
            zeroline=False,
            autorange="reversed",  # Shows highest values at top
            fixedrange=True,      # Fix y-axis range to prevent stretching
            showgrid=False
        ),
        # Keep the plot wide; leave just enough room for outside labels.
        'margin': dict(l=60, r=120, t=110, b=90),
        'updatemenus': buttons,
        # Remove the animation slider to prevent horizontal dragging/scrubbing.
        'sliders': [],
        'title': dict(
            text=full_title,
            y=0.95
        ),
        # Prevent layout resize during animations
        'transition': {
            'duration': 300,
            'easing': 'cubic-in-out'
        }
    }
    
    # Only add the year annotation if requested
    if use_default_annotation:
        layout_update['annotations'] = create_year_annotation(year)
    
    # Update layout with built settings
    fig.update_layout(**layout_update)
    # Ensure value labels never overlap bars / clip at the right edge.
    fig.update_traces(
        cliponaxis=False,
        textposition="outside",
        # Add a small visual gap between bar end and label text.
        # An en-space is a good "small but visible" offset across fonts.
        texttemplate="\u2002%{text}",
        selector=dict(type="bar"),
    )
    
    # Important: Ensure all frames use a consistent scale
    if hasattr(fig, "frames") and fig.frames:
        fix_frame_animations(fig, padded_max_value, tick_vals, tick_text)
        
        # Update each frame to include a year annotation that changes with animation
        if use_default_annotation:
            for frame in fig.frames:
                if frame.name.isdigit():
                    # Create year annotation for this specific frame
                    frame_year = int(frame.name)
                    if not hasattr(frame, 'layout') or frame.layout is None:
                        frame.layout = {}
                    frame.layout.annotations = create_year_annotation(frame_year)
    
    return fig

def fix_frame_animations(fig, max_value, tick_vals, tick_text):
    """
    Ensure all frames in the figure use a consistent scale and axis settings
    
    Args:
        fig: Plotly figure with frames
        max_value: Maximum value for consistent x-axis scaling
        tick_vals: X-axis tick values
        tick_text: X-axis tick labels
    """
    if not hasattr(fig, "frames") or not fig.frames:
        return
    
    # Update each frame to use consistent settings
    for frame in fig.frames:
        if hasattr(frame, "layout") and frame.layout:
            # Update x-axis settings for consistent scaling
            if hasattr(frame.layout, "xaxis"):
                frame.layout.xaxis.range = [0, max_value]
                frame.layout.xaxis.tickmode = 'array'
                frame.layout.xaxis.tickvals = tick_vals
                frame.layout.xaxis.ticktext = tick_text
                frame.layout.xaxis.fixedrange = True
                # Let Plotly use the full available width.
            
            # Update y-axis settings to prevent stretching
            if hasattr(frame.layout, "yaxis"):
                frame.layout.yaxis.autorange = "reversed"
                frame.layout.yaxis.fixedrange = True

def create_consistent_frame(companies, values, year, max_overall_value, 
                       title, tick_vals, tick_text, format_func, 
                       hover_template="<b>%{customdata[0]}</b><br>Value: %{customdata[1]}<extra></extra>",
                       colors=None):
    """
    Create a frame with consistent settings for bar charts
    
    Args:
        companies: List of company names
        values: List of values to plot
        year: Year for this frame
        max_overall_value: Maximum value across all years (for consistent scaling)
        title: Title prefix for the chart
        tick_vals: X-axis tick values
        tick_text: X-axis tick labels
        format_func: Function to format values for display
        hover_template: Template for hover text
        colors: List of colors for the bars (optional)
        
    Returns:
        A frame object with consistent settings
    """
    # Generate formatted text values
    text_values = [format_func(val) for val in values]
    
    # Create customdata for hover information
    custom_data = [[company, format_func(val)] for company, val in zip(companies, values)]
    
    # Use default colors if none provided
    if colors is None:
        colors = ['#636EFA'] * len(companies)
    
    # Create the frame with consistent layout
    padded_max_overall = max_overall_value * 1.10 if max_overall_value else max_overall_value
    frame = go.Frame(
        data=[go.Bar(
            y=companies,
            x=values,
            orientation='h',
            name=f"{title} {year}",
            textposition='outside',
            # Add a small horizontal gap between bar end and label.
            texttemplate='\u2002%{text}',
            text=text_values,
            cliponaxis=False,
            hovertemplate=hover_template,
            customdata=custom_data,
            marker=dict(
                color=colors,
                line=dict(color=colors, width=14),
            )
        )],
        layout=go.Layout(
            xaxis=dict(
                range=[0, padded_max_overall],
                tickmode='array',
                tickvals=tick_vals,
                ticktext=tick_text,
                fixedrange=True,
            ),
            yaxis=dict(
                autorange="reversed",
                fixedrange=True
            ),
            dragmode=False,
            transition={'duration': 300, 'easing': 'cubic-in-out'}
        ),
        name=str(year)
    )
    
    return frame

def get_dynamic_tick_values(max_value, is_trillion=False):
    """
    Generate tick values and text based on data scale
    
    Args:
        max_value: Maximum value for the axis
        is_trillion: True if using trillion scale
    
    Returns:
        Tuple of (tick_vals, tick_text)
    """
    if is_trillion:
        # For trillion-scale values
        tick_interval = 200000  # 200B intervals
        # Make sure we have at least 5 ticks
        while (max_value / tick_interval) < 5:
            tick_interval = tick_interval // 2
        tick_vals = list(range(0, int(max_value) + tick_interval, tick_interval))
        tick_text = [f"${val/1000000:.1f}T" if val >= 1000000 else f"${val/1000:.0f}B" for val in tick_vals]
    else:
        # For billion-scale values
        tick_interval = 100000  # 100B intervals
        # Make sure we have at least 5 ticks
        while (max_value / tick_interval) < 5:
            tick_interval = tick_interval // 2
        tick_vals = list(range(0, int(max_value) + tick_interval, tick_interval))
        tick_text = [f"${val/1000:.0f}B" for val in tick_vals]
        
    return tick_vals, tick_text
