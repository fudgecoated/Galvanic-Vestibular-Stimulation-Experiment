% Data
chunks = {'Control', 'GVS', 'Control', 'No vision #2', 'Control', 'GVS #2', 'Control', 'GVS;no vision; weight #2', 'Control', 'GVS; no vision', 'Control', 'No vision', 'Control', 'GVS; no vision; weight', 'Control', 'GVS; no vision #2'};
portion_right = [70, 55, 65, 20, 70, 65, 45, 20, 60, 100, 65, 10, 50, 10, 50, 100]; % in percentage
portion_left = 100 - portion_right;

% Plotting
figure;
barh(1:numel(chunks), [portion_left; portion_right]', 'stacked');
yticks(1:numel(chunks));
yticklabels(chunks);
xlabel('Proportion (%)');
title('Proportion of points in the bullseye (Left vs Right)');
legend('Left', 'Right', 'Location', 'southoutside');
xlim([0, 100]);
grid on;
