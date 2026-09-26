clc;
clear;
close all;


P = 4;             
Rs = 0.5;           
Rr = 0.3;           
Lls = 0.002;        
Llr = 0.002;       
Vs = 230;          
f = 50;
f1=70;

ws = 2*pi*f; 
ws1=2*pi*f1;
Ns = 120*f/P;                   


s = linspace(0.001, 1, 1000);   

Te = (3 * P .* (Rr ./ (s * ws)) .* Vs.^2) ./ ...
     ((Rs + Rr./s).^2 + (ws^2) * (Lls + Llr).^2);
Te1 = (3 * P .* (Rr ./ (s * ws)) .* 200.^2) ./ ...
     ((Rs + Rr./s).^2 + (ws^2) * (Lls + Llr).^2);

N = (1 - s) * Ns;

figure;
plot(N, Te, 'LineWidth', 1);
hold on;
plot(N,Te1, 'LineWidth', 2);
xlabel('Rotor Speed (RPM)');
ylabel('Electromagnetic Torque (Nm)');
title('Torque-Speed Characteristic of Induction Motor');
grid on;

set(gca, 'XDir', 'reverse');