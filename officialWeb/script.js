// ── modInteractive Landing Page Script ──

// Mobile menu toggle
function toggleMenu() {
    const nav = document.querySelector('.nav-links');
    nav.classList.toggle('active');
}

// Close mobile menu on link click
document.querySelectorAll('.nav-links a').forEach(link => {
    link.addEventListener('click', () => {
        document.querySelector('.nav-links').classList.remove('active');
    });
});

// Copy code to clipboard
function copyCode(btn) {
    const codeBlock = btn.nextElementSibling;
    const text = codeBlock.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        const original = btn.textContent;
        btn.textContent = '✅';
        setTimeout(() => {
            btn.textContent = original;
        }, 2000);
    }).catch(() => {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        
        const original = btn.textContent;
        btn.textContent = '✅';
        setTimeout(() => {
            btn.textContent = original;
        }, 2000);
    });
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});

// Intersection Observer for scroll animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe feature cards, spec cards, and install steps
document.querySelectorAll('.feature-card, .spec-card, .install-step, .flow-step').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
});

// Parallax effect on hero
document.addEventListener('mousemove', (e) => {
    const cards = document.querySelectorAll('.floating-card');
    const x = (e.clientX / window.innerWidth - 0.5) * 10;
    const y = (e.clientY / window.innerHeight - 0.5) * 10;
    
    cards.forEach((card, i) => {
        const speed = (i + 1) * 0.5;
        card.style.transform = `translate(${x * speed}px, ${y * speed}px)`;
    });
});

// Dynamic stats counter animation
function animateCounter(el, target, suffix = '') {
    let current = 0;
    const increment = Math.ceil(target / 60);
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        el.textContent = current + suffix;
    }, 20);
}

// Animate stats when visible
const statsObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const values = entry.target.querySelectorAll('.stat-value');
            const targets = ['8', '101', '0', '24/7'];
            values.forEach((el, i) => {
                const num = parseInt(targets[i]);
                if (!isNaN(num)) {
                    animateCounter(el, num);
                } else {
                    el.textContent = targets[i];
                }
            });
            statsObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.5 });

document.querySelectorAll('.hero-stats').forEach(el => statsObserver.observe(el));

// Console Easter Egg
console.log('%c◆ modInteractive', 'font-size: 24px; font-weight: bold; color: #4a90d9;');
console.log('%cAI-Powered Kiosk System for Raspberry Pi 5', 'font-size: 14px; color: #8888aa;');
console.log('%cBuilt with ❤️ by WATAM', 'font-size: 12px; color: #8888aa;');
console.log('%chttps://WeAreTheArtMakers.com', 'font-size: 12px; color: #4a90d9;');