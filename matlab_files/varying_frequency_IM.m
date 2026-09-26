clc;
clear;
close all;


P = 4;
Rs = 0.5;
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

        V = V_base * (f/f_base);   
   

    Te = (3 * P .* (Rr ./ (s * ws)) .* V.^2) ./ ...
        ((Rs + Rr./s).^2 + (ws^2) * (Lls + Llr).^2);
    

    N = (1 - s) * Ns;
    
    plot(N, Te, 'LineWidth', 2);
end

% ----------- Plot formatting -----------
xlabel('Speed (RPM)');
ylabel('Torque (Nm)');
title('Torque-Speed Curves (Field Weakening Region)');
grid on;

legend('50 Hz','75 Hz','100 Hz','125 Hz','150 Hz');

% Reverse x-axis (like textbook plots)
set(gca, 'XDir', 'reverse');