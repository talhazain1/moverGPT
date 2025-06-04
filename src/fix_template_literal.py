import os

def fix_cost_calculator_html():
    file_path = os.path.join('static', 'cost_calculator.html')
    print(f"Looking for file at: {os.path.abspath(file_path)}")
    
    try:
        # Read the current file
        with open(file_path, 'r') as file:
            content = file.read()
            print(f"Read file, size: {len(content)} characters")
        
        # Find the problematic generateEmbedCode function and replace it
        start_marker = "function generateEmbedCode(companyId, apiUrl) {"
        end_marker = "document.getElementById('embed-code').textContent = embedCode.trim();"
        
        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker) + len(end_marker)
        
        print(f"Found start_idx: {start_idx}, end_idx: {end_idx}")
        
        if start_idx == -1 or end_idx == -1:
            print("Could not find the generateEmbedCode function in the file.")
            return False
        
        print("Found function to replace, creating fixed version...")
        
        # Create the fixed function
        fixed_function = """function generateEmbedCode(companyId, apiUrl) {
        const embedCode = [
          '<!-- Moving Cost Calculator Widget -->',
          '<div id="moving-cost-calculator-container"></div>',
          '<script>',
          '    (function() {',
          '        var script = document.createElement(\\'script\\');',
          '        script.src = \\'' + apiUrl + '/static/moving-calculator/js/widget.js\\';',
          '        script.async = true;',
          '        script.onload = function() {',
          '            initMovingCalculator({',
          '                companyId: ' + companyId + ',',
          '                apiUrl: \\'' + apiUrl + '\\',',
          '                containerId: \\'moving-cost-calculator-container\\',',
          '                primaryColor: \\'#4A6FDC\\',',
          '                secondaryColor: \\'#6c757d\\',',
          '                fontFamily: \\'Arial, sans-serif\\'',
          '            });',
          '        };',
          '        document.head.appendChild(script);',
          '        ',
          '        var link = document.createElement(\\'link\\');',
          '        link.rel = \\'stylesheet\\';',
          '        link.href = \\'' + apiUrl + '/static/moving-calculator/css/widget.css\\';',
          '        document.head.appendChild(link);',
          '    })();',
          '</script>',
          '<!-- End Moving Cost Calculator Widget -->'
        ].join('\\n');
        
        document.getElementById('embed-code').textContent = embedCode;"""
        
        # Replace the problematic code with the fixed version
        fixed_content = content[:start_idx] + fixed_function + content[end_idx:]
        print(f"Created fixed content, size: {len(fixed_content)} characters")
        
        # Create a backup
        backup_path = file_path + '.bak'
        with open(backup_path, 'w') as backup_file:
            backup_file.write(content)
            print(f"Created backup at {backup_path}")
        
        # Write the fixed content
        with open(file_path, 'w') as file:
            file.write(fixed_content)
            print(f"Wrote fixed content to {file_path}")
        
        print(f"Fixed cost_calculator.html! Backup saved at {backup_path}")
        return True
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Starting fix script...")
    result = fix_cost_calculator_html()
    print(f"Script completed with result: {result}") 