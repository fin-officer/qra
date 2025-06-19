// Blog Template JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 80, // Offset for fixed header
                    behavior: 'smooth'
                });
            }
        });
    });

    // Reading progress bar
    const progressBar = document.createElement('div');
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 0%;
        height: 3px;
        background: #3498db;
        z-index: 1000;
        transition: width 0.3s;
    `;
    document.body.appendChild(progressBar);

    // Update progress bar on scroll
    function updateProgressBar() {
        const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
        const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const scrolled = (winScroll / height) * 100;
        progressBar.style.width = scrolled + '%';
    }

    window.addEventListener('scroll', updateProgressBar);
    updateProgressBar(); // Initial call

    // Smooth reveal animation for post content
    const postContent = document.querySelector('.post-content');
    if (postContent) {
        const elements = postContent.querySelectorAll('h2, h3, p, ul, ol, blockquote, pre, img');

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, { 
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        });

        elements.forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(20px)';
            el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
            observer.observe(el);
        });
    }


    // Add copy button to code blocks
    document.querySelectorAll('pre').forEach(pre => {
        // Create copy button
        const button = document.createElement('button');
        button.className = 'copy-button';
        button.textContent = 'Kopiuj';
        button.style.cssText = `
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            padding: 0.25rem 0.5rem;
            background: #f1f3f4;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.8rem;
            cursor: pointer;
            opacity: 0;
            transition: opacity 0.3s, background 0.2s;
        `;
        
        pre.style.position = 'relative';
        pre.appendChild(button);

        // Show/hide button on hover
        pre.addEventListener('mouseenter', () => {
            button.style.opacity = '1';
        });

        pre.addEventListener('mouseleave', () => {
            if (button.textContent !== 'Skopiowano!') {
                button.style.opacity = '0';
            }
        });

        // Copy code on button click
        button.addEventListener('click', () => {
            const code = pre.querySelector('code')?.innerText || pre.innerText;
            navigator.clipboard.writeText(code).then(() => {
                const originalText = button.textContent;
                button.textContent = 'Skopiowano!';
                button.style.background = '#4caf50';
                button.style.color = 'white';
                button.style.borderColor = '#4caf50';
                button.style.opacity = '1';
                
                setTimeout(() => {
                    button.textContent = originalText;
                    button.style.background = '';
                    button.style.color = '';
                    button.style.borderColor = '';
                    button.style.opacity = '0';
                }, 2000);
            });
        });
    });
});
