/**
 * LandingFooter - Footer component for the landing page
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Github, Twitter, Linkedin, Mail } from 'lucide-react';
import logo from '../../../assets/logo.png';

const footerLinks = {
  product: {
    title: 'Product',
    links: [
      { label: 'Features', href: '#' },
      { label: 'Marketplace', href: '/marketplace' },
      { label: 'Pricing', href: '#' },
      { label: 'Integrations', href: '#' }
    ]
  },
  solutions: {
    title: 'Solutions',
    links: [
      { label: 'Enterprise', href: '#' },
      { label: 'Developers', href: '#' },
      { label: 'Business Users', href: '#' },
      { label: 'API', href: '#' }
    ]
  },
  resources: {
    title: 'Resources',
    links: [
      { label: 'Documentation', href: '#' },
      { label: 'Tutorials', href: '#' },
      { label: 'Blog', href: '#' },
      { label: 'Community', href: '#' }
    ]
  },
  company: {
    title: 'Company',
    links: [
      { label: 'About', href: '#' },
      { label: 'Careers', href: '#' },
      { label: 'Contact', href: '#' },
      { label: 'Privacy', href: '#' }
    ]
  }
};

const socialLinks = [
  { icon: Twitter, href: '#', label: 'Twitter' },
  { icon: Github, href: '#', label: 'GitHub' },
  { icon: Linkedin, href: '#', label: 'LinkedIn' },
  { icon: Mail, href: 'mailto:hello@ioflow.com', label: 'Email' }
];

const LandingFooter = () => {
  const navigate = useNavigate();

  const handleNavigation = (href) => {
    if (href.startsWith('/')) {
      navigate(href);
    } else if (href.startsWith('mailto:')) {
      window.location.href = href;
    }
  };

  return (
    <footer className="bg-gray-900 text-gray-300">
      {/* Main Footer */}
      <div className="max-w-7xl mx-auto px-4 py-12 md:py-16">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-8">
          {/* Brand Column */}
          <div className="col-span-2">
            <div className="flex items-center gap-3 mb-4">
              <img src={logo} alt="IOFlow" className="w-10 h-10 rounded-lg" />
              <span className="text-xl font-bold text-white">IOFlow</span>
            </div>
            <p className="text-gray-400 mb-6 max-w-xs">
              Enterprise-grade automation for everyone. Build workflows, create Micro SaaS apps, and automate your business.
            </p>

            {/* Social Links */}
            <div className="flex items-center gap-4">
              {socialLinks.map((social) => {
                const Icon = social.icon;
                return (
                  <a
                    key={social.label}
                    href={social.href}
                    className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
                    aria-label={social.label}
                  >
                    <Icon className="w-5 h-5" />
                  </a>
                );
              })}
            </div>
          </div>

          {/* Link Columns */}
          {Object.entries(footerLinks).map(([key, section]) => (
            <div key={key}>
              <h4 className="text-white font-semibold mb-4">{section.title}</h4>
              <ul className="space-y-3">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <button
                      onClick={() => handleNavigation(link.href)}
                      className="text-gray-400 hover:text-white transition-colors text-left"
                    >
                      {link.label}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-gray-800">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-gray-500 text-sm">
              &copy; {new Date().getFullYear()} IOFlow. All rights reserved.
            </p>
            <div className="flex items-center gap-6 text-sm">
              <button
                onClick={() => handleNavigation('#')}
                className="text-gray-500 hover:text-white transition-colors"
              >
                Terms of Service
              </button>
              <button
                onClick={() => handleNavigation('#')}
                className="text-gray-500 hover:text-white transition-colors"
              >
                Privacy Policy
              </button>
              <button
                onClick={() => handleNavigation('#')}
                className="text-gray-500 hover:text-white transition-colors"
              >
                Cookie Policy
              </button>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default LandingFooter;
