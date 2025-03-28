(function(__name) {
    // hook console
    const console = (function(__name) {
        return {
            log: (...args) => window.console.log(`[${__name}]`, ...args),
            info: (...args) => window.console.info(`[${__name}]`, ...args),
            warn: (...args) => window.console.warn(`[${__name}]`, ...args),
            error: (...args) => window.console.error(`[${__name}]`, ...args),
            debug: (...args) => window.console.debug(`[${__name}]`, ...args),
        };
    })(__name);

    // ========================================================================
    try {
        (function() {
            $CODE
        })();
    } catch (error) {
        window.console.error('Error:', error);
    }
    // ========================================================================
})($NAME);
