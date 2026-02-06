"""
Provides CSS-based bar animations as an alternative to Plotly animations
for better performance in the Overview page.
"""

def get_bar_animation_css():
    """
    Returns CSS for optimized bar chart animations using CSS transitions
    instead of JavaScript animations. Creates a container with fixed width
    and animates the bar to fill that container.
    """
    return """
    <style>
        /* Container for the entire bar chart */
        .bar-chart-container {
            margin: 30px 0;
            font-family: 'Montserrat', sans-serif;
            max-width: 95%;
            width: 100%;
            margin-left: auto;
            margin-right: auto;
        }
        
        /* Row container for each bar and its label */
        .bar-row {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            position: relative;
        }
        
        /* Company label styling */
        .bar-label {
            width: 140px;
            flex-shrink: 0;
            font-size: 14px;
            text-align: right;
            padding-right: 15px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: #333;
            font-weight: 500;
        }
        
        /* Outer container with fixed width */
        .bar-container {
            position: relative;
            background-color: #f2f2f2;
            border-radius: 4px;
            height: 25px;
            flex-grow: 1;
            overflow: hidden;
            margin-right: 80px; /* Add margin to prevent value cutoff */
        }
        
        /* The animated bar itself */
        .bar {
            height: 100%;
            width: 0%;
            border-radius: 4px;
            position: relative;
            transition: width 1s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        }
        
        /* Value display on the right of each bar */
        .bar-value {
            position: absolute;
            right: -70px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 14px;
            color: #666;
            width: 120px;
            padding-left: 10px;
            white-space: nowrap;
        }
        
        /* Animation delay for sequential animation */
        .bar-1 { animation-delay: 0s; }
        .bar-2 { animation-delay: 0.15s; }
        .bar-3 { animation-delay: 0.30s; }
        .bar-4 { animation-delay: 0.45s; }
        .bar-5 { animation-delay: 0.60s; }
        .bar-6 { animation-delay: 0.75s; }
        .bar-7 { animation-delay: 0.90s; }
        .bar-8 { animation-delay: 1.05s; }
        .bar-9 { animation-delay: 1.20s; }
        .bar-10 { animation-delay: 1.35s; }
        .bar-11 { animation-delay: 1.50s; }
        .bar-12 { animation-delay: 1.65s; }
        .bar-13 { animation-delay: 1.80s; }
        .bar-14 { animation-delay: 1.95s; }
        .bar-15 { animation-delay: 2.10s; }
        .bar-16 { animation-delay: 2.25s; }
        .bar-17 { animation-delay: 2.40s; }
        .bar-18 { animation-delay: 2.55s; }
        .bar-19 { animation-delay: 2.70s; }
        .bar-20 { animation-delay: 2.85s; }
        
        /* Apply animation to bars with the 'animate' class */
        .bar.animate {
            animation: bar-animation 1s forwards;
        }
        
        /* Animation to fill the bar */
        @keyframes bar-animation {
            from { width: 0%; }
            to { width: var(--fill-percent, 100%); }
        }
        
        /* Title for the chart */
        .bar-chart-title {
            font-family: 'Montserrat', sans-serif;
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
            color: #333;
        }
        
        /* Animation for year display */
        .year-indicator {
            font-family: 'Montserrat', sans-serif;
            font-size: 24px;
            font-weight: 700;
            text-align: center;
            margin-bottom: 30px;
            color: #333;
            opacity: 0;
            animation: fade-in 0.5s forwards;
        }
        
        @keyframes fade-in {
            from { opacity: 0; }
            to { opacity: 1; }
        }
    </style>
    """

def render_bar_chart(title, data, max_value=None, bar_colors=None):
    """
    Generates HTML for a CSS-based animated bar chart
    
    Args:
        title: Chart title
        data: List of dictionaries with 'label' and 'value' keys
        max_value: Maximum value for scaling (if None, will use max from data)
        bar_colors: List of color codes for bars (if None, will use default colors)
    
    Returns:
        HTML string for the chart
    """
    if not data:
        return "<div class='bar-chart-container'>No data available</div>"
    
    # Sort data by value in descending order
    sorted_data = sorted(data, key=lambda x: x['value'] if x['value'] is not None else 0, reverse=True)
    
    # Determine max value for scaling
    if max_value is None:
        values = [item['value'] for item in sorted_data if item['value'] is not None]
        max_value = max(values) if values else 1
    
    # Default colors if not provided
    if bar_colors is None:
        default_colors = [
            "#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f",
            "#edc949", "#af7aa1", "#ff9da7", "#9c755f", "#bab0ab"
        ]
        bar_colors = default_colors
    
    # Format the value based on its magnitude with improved precision for large values
    def format_value(val):
        if val is None:
            return "N/A"
        elif val >= 1000000000000:  # Trillions
            return f"${val/1000000000000:.2f}T"
        elif val >= 1000000000:  # Billions
            if val >= 100000000000:  # Over 100 billion
                return f"${val/1000000000:.1f}B"
            else:
                return f"${val/1000000000:.2f}B"
        elif val >= 1000000:  # Millions
            return f"${val/1000000:.1f}M"
        elif val >= 1000:  # Thousands
            return f"${val/1000:.1f}K"
        else:
            return f"${val:.0f}"
    
    html = f"""
    <div class="bar-chart-container">
        <div class="bar-chart-title">{title}</div>
    """
    
    for i, item in enumerate(sorted_data):
        label = item['label']
        value = item['value']
        
        if value is None:
            fill_percent = 0
            display_value = "N/A"
        else:
            # Calculate fill percentage based on max value (scale to 85% to leave more room for value display)
            # Add a 5% safety margin to max_value to prevent the chart from filling up completely
            fill_percent = min(85, (value / (max_value * 1.05)) * 85)
            display_value = format_value(value)
        
        # Get color (cycle through colors if we have more items than colors)
        color = bar_colors[i % len(bar_colors)]
        
        html += f"""
        <div class="bar-row">
            <div class="bar-label">{label}</div>
            <div class="bar-container">
                <div class="bar bar-{i+1}" 
                     style="--fill-percent: {fill_percent}%; background-color: {color};"
                     id="bar-{i+1}-{hash(label) % 10000}"></div>
            </div>
            <div class="bar-value">{display_value}</div>
        </div>
        """
    
    html += """
    </div>
    <script>
        // Function to animate bars with a slight delay between each
        function animateBars() {
            const bars = document.querySelectorAll('.bar');
            bars.forEach((bar, index) => {
                setTimeout(() => {
                    bar.style.width = bar.style.getPropertyValue('--fill-percent');
                }, index * 120);  // Reduced to 120ms delay between each bar to accommodate more companies
            });
        }
        
        // Trigger animation when the content is visible
        document.addEventListener('DOMContentLoaded', () => {
            // Use a small timeout to ensure the DOM is fully rendered
            setTimeout(animateBars, 300);
        });
        
        // Re-trigger animation when this element comes into view
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // Reset all bars to 0 width first
                    const bars = document.querySelectorAll('.bar');
                    bars.forEach(bar => {
                        bar.style.width = '0%';
                    });
                    
                    // Then animate them again after a short delay
                    setTimeout(animateBars, 200);
                }
            });
        }, { threshold: 0.1 });
        
        // Observe the container
        const container = document.querySelector('.bar-chart-container');
        if (container) {
            observer.observe(container);
        }
    </script>
    """
    
    return html

def generate_year_selector_html(years, current_year):
    """
    Generates HTML for a year selector with buttons
    
    Args:
        years: List of available years
        current_year: Currently selected year
    
    Returns:
        HTML string for the year selector
    """
    html = """
    <div id="financial-year-selector" class="year-selector" style="display: flex; flex-wrap: wrap; justify-content: center; margin: 20px 0; max-width: 100%; overflow-x: auto;">
    """
    
    for year in sorted(years):
        active_class = "active" if str(year) == str(current_year) else ""
        html += f"""
        <button 
            class="year-button {active_class}" 
            data-year="{year}"
            style="margin: 3px; padding: 6px 12px; background-color: {'#ff4202' if str(year) == str(current_year) else '#f0f0f0'}; 
                   color: {'white' if str(year) == str(current_year) else '#333'}; border: none; border-radius: 20px; 
                   cursor: pointer; font-family: sans-serif; font-weight: 500; 
                   transition: all 0.3s ease;"
        >{year}</button>
        """
    
    html += """
    </div>
    <script>
        (function() {
            // Execute immediately to avoid DOM ready delays
            // Function to update buttons and set year
            function setYearAndUpdateButtons(year) {
                // Get all year buttons
                const yearButtons = document.querySelectorAll('.year-button');
                if (!yearButtons || yearButtons.length === 0) return;
                
                // Update active state
                yearButtons.forEach(btn => {
                    const btnYear = btn.getAttribute('data-year');
                    const isActive = btnYear === year;
                    btn.classList.toggle('active', isActive);
                    btn.style.backgroundColor = isActive ? '#ff4202' : '#f0f0f0';
                    btn.style.color = isActive ? 'white' : '#333';
                });
                
                // Update URL parameters
                const params = new URLSearchParams(window.location.search);
                params.set('selected_year', year);
                window.location.search = params.toString();
            }
            
            // Add click handlers to year buttons (with timeout to ensure DOM is ready)
            setTimeout(() => {
                const yearButtons = document.querySelectorAll('.year-button');
                yearButtons.forEach(button => {
                    button.addEventListener('click', (e) => {
                        e.preventDefault();
                        const year = e.target.getAttribute('data-year');
                        setYearAndUpdateButtons(year);
                    });
                    
                    // Add hover effects
                    button.addEventListener('mouseover', (e) => {
                        if (!e.target.classList.contains('active')) {
                            e.target.style.backgroundColor = '#e0e0e0';
                        }
                    });
                    
                    button.addEventListener('mouseout', (e) => {
                        if (!e.target.classList.contains('active')) {
                            e.target.style.backgroundColor = '#f0f0f0';
                        }
                    });
                });
            }, 200);
        })();
    </script>
    """
    
    return html
