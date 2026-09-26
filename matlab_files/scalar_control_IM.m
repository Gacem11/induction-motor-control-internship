clc;
clear;
close all;


P = 4;
Rs = 0.2;              
Rr = 0.3;
Lls = 0.002;
Llr = 0.002;

V_base = 230;      
f_base = 50;       

s = linspace(0.001, 1, 1000);

f_list = [50 35 20 15 10];

figure;
hold on;

for f = f_list
    
    ws = 2*pi*f;            
    Ns = 120*f/P;            
    
    % V/f constant
    V = V_base * (f/f_base)+11.5;   
    
    % Torque equation
    Te = (3 * P .* (Rr ./ (s * ws)) .* V.^2) ./ ...
        ((Rs + Rr./s).^2 + (ws^2) * (Lls + Llr).^2);
    
    % Speed
    N = (1 - s) * Ns;
    
    plot(N, Te, 'LineWidth', 2);
end

% ----------- Plot formatting -----------
xlabel('Speed (RPM)');
ylabel('Torque (Nm)');
title('Ideal Constant Torque Region (V/f Control)');
grid on;

legend('50 Hz','35 Hz','20 Hz','15 Hz','10 Hz');

% Reverse x-axis
set(gca, 'XDir', 'reverse');