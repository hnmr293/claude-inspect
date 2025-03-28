({
    /**
     * operations:
     *   - apply_chat()
     *   - put_chat(text: string)
     *   - clear_chat()
     */

    apply_chat: function() {
        return new Promise((resolve, reject) => {
            const inputElem = document.querySelector('.ProseMirror p');
            if (inputElem) {
                inputElem.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            } else {
                reject('Input element not found');
            }
            function check() {
                if (inputElem.innerText === '') {
                    resolve();
                } else {
                    setTimeout(check, 10);
                }
            }
            setTimeout(check, 10);
        });
    },

    put_chat: function(text) {
        return new Promise((resolve, reject) => {
            const inputElem = document.querySelector('.ProseMirror p');
            if (inputElem) {
                inputElem.innerText = text;
                resolve();
            }
            else {
                reject('Input element not found');
            }
        });
    },

    clear_chat: function() {
        return new Promise((resolve, reject) => {
            const inputElem = document.querySelector('.ProseMirror p');
            if (inputElem) {
                inputElem.innerText = '';
                resolve();
            } else {
                reject('Input element not found');
            }
        });
    },

})