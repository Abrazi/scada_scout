"""Simple test script for debugger verification"""

def main(ctx):
    """Test debugger with variables and stepping"""
    ctx.log('info', 'Debugger test started')
    
    # Test variables
    counter = 0
    message = "Hello from debugger"
    numbers = [1, 2, 3, 4, 5]
    
    # Test loop with breakpoint opportunity
    for i in range(5):
        counter += i
        result = counter * 2
        ctx.log('info', f'Iteration {i}: counter={counter}, result={result}')
    
    # Test dictionary
    data = {
        'name': 'Test Device',
        'value': counter,
        'status': 'active'
    }
    
    ctx.log('info', f'Final result: {data}')
    ctx.log('info', 'Debugger test completed')
