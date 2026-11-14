/**
 * PricingPreview - Simple pricing tiers preview
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Zap, Building2, Rocket } from 'lucide-react';

const tiers = [
  {
    id: 'free',
    name: 'Free',
    description: 'Perfect for getting started',
    price: '$0',
    period: 'forever',
    icon: Zap,
    features: [
      '5 flows per month',
      'Basic integrations',
      'Community support',
      'Public marketplace access'
    ],
    cta: 'Start Free',
    ctaVariant: 'outline',
    highlight: false
  },
  {
    id: 'pro',
    name: 'Pro',
    description: 'For serious automation',
    price: '$29',
    period: 'per month',
    icon: Rocket,
    features: [
      'Unlimited flows',
      'All integrations',
      'Priority support',
      'Advanced analytics',
      'Custom webhooks',
      'Team collaboration'
    ],
    cta: 'Start Pro Trial',
    ctaVariant: 'primary',
    highlight: true
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    description: 'For large organizations',
    price: 'Custom',
    period: 'contact us',
    icon: Building2,
    features: [
      'Everything in Pro',
      'SSO / SAML',
      'Dedicated support',
      'Custom integrations',
      'SLA guarantee',
      'On-premise option'
    ],
    cta: 'Contact Sales',
    ctaVariant: 'outline',
    highlight: false
  }
];

const PricingPreview = () => {
  const navigate = useNavigate();

  const handleCta = (tierId) => {
    if (tierId === 'enterprise') {
      // Could open a contact form modal
      window.location.href = 'mailto:sales@ioflow.com?subject=Enterprise Inquiry';
    } else {
      navigate('/register');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4">
      {/* Header */}
      <div className="text-center mb-12">
        <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
          Simple, Transparent Pricing
        </h2>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          Start free and scale as you grow. No hidden fees, no surprises.
        </p>
      </div>

      {/* Pricing Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
        {tiers.map((tier) => {
          const Icon = tier.icon;
          return (
            <div
              key={tier.id}
              className={`
                relative bg-white rounded-2xl p-6 lg:p-8 transition-all duration-300
                ${tier.highlight
                  ? 'border-2 border-primary shadow-xl shadow-primary/20 scale-105'
                  : 'border border-gray-200 shadow-lg hover:shadow-xl'}
              `}
            >
              {/* Popular Badge */}
              {tier.highlight && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-gradient-accent text-white text-sm font-medium rounded-full">
                  Most Popular
                </div>
              )}

              {/* Icon */}
              <div className={`
                inline-flex items-center justify-center w-12 h-12 rounded-xl mb-4
                ${tier.highlight ? 'bg-gradient-to-br from-primary/20 to-secondary/20 text-primary' : 'bg-gray-100 text-gray-600'}
              `}>
                <Icon className="w-6 h-6" />
              </div>

              {/* Name & Description */}
              <h3 className="text-xl font-bold text-gray-900 mb-1">{tier.name}</h3>
              <p className="text-gray-600 text-sm mb-4">{tier.description}</p>

              {/* Price */}
              <div className="mb-6">
                <span className="text-4xl font-bold text-gray-900">{tier.price}</span>
                <span className="text-gray-500 ml-2">/ {tier.period}</span>
              </div>

              {/* Features */}
              <ul className="space-y-3 mb-8">
                {tier.features.map((feature, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <Check className={`
                      w-5 h-5 flex-shrink-0 mt-0.5
                      ${tier.highlight ? 'text-primary' : 'text-primary'}
                    `} />
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>

              {/* CTA Button */}
              <button
                onClick={() => handleCta(tier.id)}
                className={`
                  w-full py-3 px-6 rounded-lg font-semibold transition-all duration-300
                  ${tier.ctaVariant === 'primary'
                    ? 'bg-gradient-accent text-white hover:from-[#dc6b7e] hover:to-[#e8915c] shadow-lg hover:shadow-xl'
                    : 'bg-white border-2 border-gray-200 text-gray-700 hover:border-primary hover:text-primary'}
                `}
              >
                {tier.cta}
              </button>
            </div>
          );
        })}
      </div>

      {/* Additional Info */}
      <div className="mt-12 text-center">
        <p className="text-gray-500">
          All plans include a 14-day free trial. No credit card required.
        </p>
      </div>
    </div>
  );
};

export default PricingPreview;
