clc;
clear;
close all;


Rs_pu = 0.05;    
Xs_base = 0.1;    
I_pu = 1;         
phi_pu = 1;       

w_pu = linspace(0, 2, 500);   

V_pu = zeros(size(w_pu));

for i = 1:length(w_pu)
    
    % reactance varies with frequency
    X_pu = w_pu(i) * Xs_base;
    
    % from KVL
    V_pu(i) = w_pu(i)*phi_pu + I_pu * sqrt(Rs_pu^2 + X_pu^2);
    
    % voltage limit (field weakening)
    if V_pu(i) > 1
        V_pu(i) = 1;
    end
end

% -------- Plot -----------
figure;
plot(w_pu, V_pu, 'LineWidth', 2);
grid on;

xlabel('Frequency (pu)');
ylabel('Voltage (pu)');
title('V/f Characteristic from Equivalent Circuit');

ylim([0 1.2]);
xlim([0 2]);