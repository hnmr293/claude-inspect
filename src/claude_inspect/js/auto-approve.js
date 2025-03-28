// https://gist.githubusercontent.com/Richard-Weiss/95f8bf90b55a3a41b4ae0ddd7a614942/raw/551191d897498708abcc97f928d63f463aa17f1c/claude_mcp_auto_approve.js

// Array of trusted tool names
const trustedTools = $AUTO_APPROVE_TOOLS;

// Cooldown tracking
let lastClickTime = 0;
const COOLDOWN_MS = 1000; // 1 second cooldown

const observer = new MutationObserver((mutations) => {
    // Check if we're still in cooldown
    const now = Date.now();
    if (now - lastClickTime < COOLDOWN_MS) {
        console.log('🕒 Still in cooldown period, skipping...');
        return;
    }

    console.log('🔍 Checking mutations...');
    
    const dialog = document.querySelector('[role="dialog"]');
    if (!dialog) return;

    const buttonWithDiv = dialog.querySelector('button div');
    if (!buttonWithDiv) return;

    const toolText = buttonWithDiv.textContent;
    if (!toolText) return;

    console.log('📝 Found tool request:', toolText);
    
    const toolName = toolText.match(/Run (\S+) from/)?.[1];
    if (!toolName) return;

    console.log('🛠️ Tool name:', toolName);
    
    if (trustedTools.includes(toolName)) {
        const allowButton = Array.from(dialog.querySelectorAll('button'))
            .find(button => button.textContent.includes('Allow for This Chat'));
        
        if (allowButton) {
            console.log('🚀 Auto-approving tool:', toolName);
            lastClickTime = now; // Set cooldown
            allowButton.click();
        }
    } else {
        console.log('❌ Tool not in trusted list:', toolName);
    }
});

// Start observing
console.log('👀 Starting observer for trusted tools:', trustedTools);
observer.observe(document.body, {
    childList: true,
    subtree: true
});
