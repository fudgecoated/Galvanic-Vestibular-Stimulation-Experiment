          function treadmillForceData(varargin)
%
%    See 'daqscope' in the daqdemo folder in the daq toolbox for original
%    version of code.
%


%    MP 11-05-98
%    Copyright 1998-2009 The MathWorks, Inc.
%    $Revision: 1.9.2.14 $  $Date: 2009/03/13 08:52:18 $

%    treadmillForceData -- specific revision by Lanxin Liu for HBCL,
%    University of Michigan, 5/21/2012, v1.8

%    Revised by Tian Bao to read the Handrail Data
%    University of Michigan, 12/3/2012

%%
%   INSTRUCTIONS
%   
%   1. Run program
%   2. Choose file name and destination where indicated
%   3. (Optional) Set timer for recording and samplerate
%   4. Press play to see data (not to start recording)
%   5. (Optional) Press Autoset to automatically change Y-axis
%   5.5. (Optional) Press View - Legend to see legend
%   6. Select which channels to see (does not affect recording)
%   7. Press record to record data
%   8. Wait (if timer is active) or hit the button again to stop
%   9. (Optional) Change file name (will automatically renumber anyway)
%   10. Press stop when done
%
%   Note: The data's column orders match the excel files' column orders.

%%
% Error if an output argument is supplied.
if nargout > 0
    error('Too many output arguments.');
end

%%
% Based on the number of input arguments call the appropriate
% local function.

switch nargin
    case 0
        % Create the figure and initialize variables.
        data = localInitFig;
        hFig = data.handle.figure;
    case 1
        error('No inputs required to run DAQSCOPE.');
    case 2
        % Initialize variables.
        action = varargin{1};
        hFig = varargin{2};
        data = get(hFig, 'UserData');
        
        % Call the appropriate local function based on the action.
        switch action
            case 'autoset'
                data = localAutoset(data);
            case 'changeChannel'
                data = localChangeChannel(data);
            case 'checkbox'
                data = localCheckBox(data);
            case 'checkboxtimer'
                data = localCheckBoxTimer(data);
            case 'checkpoint'
                data = localCheckpoint(data);
            case 'close'
                localClose(data);
            case 'daqhelp'
                localDaqHelp;
            case 'filename'
                data = localFileName(data);
            case 'legend'
                data = localLegend(data);
            case 'oshelp';
                localOsHelp;
            case 'sampleRate'
                data = localSampleRate(data);
            case 'savelocation'
                data = localSaveLocation(data);
            case 'start'
                data = localStart(data);
            case 'stop'
                data = localStop(data);
            case 'voltscheck'
                data = localVoltsCheck(data);
            case 'voltsrange'
                data = localVoltsRange(data);
        end
    case 3
        % Action callback.
        obj = varargin{1};
        event = varargin{2};
        action = varargin{3};
        switch action
            case 'timeraction'
                data = localTimerAction(obj, event);
                return;
            case 'checkpoint'
                data = localCheckpoint(obj);
                hFig = data.handle.figure;
        end
    case 4
        action = varargin{3};
        hFig = varargin{4};
        data = get(hFig, 'UserData');
        switch action
            case 'stopaction'
                data = localStop(data);
        end
    otherwise
        error('Too many input arguments.');
end

% Update the figure's UserData.
if exist('hFig', 'var')
    if ~isempty(hFig)&&ishandle(hFig)
        set(hFig,'UserData',data);
    end
end

%%
% Store the data structure in the analog input object.
if ~isempty(data.ai) && isvalid(data.ai)
    set(data.ai, 'UserData', data);
end

%% *******************************************************************
% Update the y-axis limits based on the incoming signal.
function data = localAutoset(data)

if ~isrunning(data.ai)
    set(data.handle.uicontrol(7), 'Value', 0);
    hWarn = findobj(findall(0), 'Tag', 'notRunningCantAutoset');
    if isempty(hWarn)
        hWarn = warndlg('The analog input acquisition must be started.',...
            'Data Acquisition Warning');
        set(hWarn, 'Tag', 'notRunningCantAutoset');
    else
        figure(hWarn(1));
    end
    return;
else
    % Turn on the Autoset radiobutton - needed in case the radiobutton
    % is selected and is selected again.
    set(data.handle.uicontrol(7), 'Value', 1);
    
    % Turn off the Volts/Div radiobutton.
    set(data.handle.uicontrol(8), 'Value', 0);
    set(data.handle.uicontrol(3), 'Enable', 'off');
    
    % Get some data to calculate the new range.
    pause(1);
    x1 = peekdata(data.ai, get(data.ai, 'SampleRate') * 5);
    try
        x2 = peekdata(data.ai2, get(data.ai2, 'SampleRate') * 5);
    catch e
        x2 = zeros(size(x1, 1), 6);
    end
    
    % Try combining the two data matrices together (fill difference in
    % dimensions with zeros)
    try
        x = horzcat(x1, x2);
    catch e
        diff = size(x2, 1) - size(x1, 1);
        more = zeros(diff, 14);
        x1 = vertcat(x1, more);
    end
    
    try
        x = horzcat(x1, x2);
    catch e
        diff = size(x1, 1) - size(x2, 1);
        more = zeros(diff, 6);
        x2 = vertcat(x2, more);
        x = horzcat(x1, x2);
    end
    
    % Set upper and lower y-axis limits, rounded to .001
    ylower = round(min(min(x(:, data.channel))) * 1000 - 1) / 1000;
    yupper = round(max(max(x(:, data.channel))) * 1000 + 1) / 1000;
    
    % If NaN's are returned base the limit off the other.
    if isnan(ylower) && isnan(yupper)
        ylower = -0.01;
        yupper = 0.01;
    elseif isnan(ylower)
        ylower = yupper - (abs(yupper)/2);
    elseif isnan(yupper)
        yupper = ylower + (abs(ylower)/2);
    end
    
    % Handle the case when the limits are equal.
    if ylower == yupper
        ylower = ylower - (abs(ylower)/2);
        yupper = yupper + (abs(yupper)/2);
    end
    
    % If they are still equal (if they both were zero).
    if ylower == yupper
        ylower = -0.01;
        yupper = 0.01;
    end
    
    %Reset the graph
    set(data.handle.axes, 'YLim', [ylower yupper],...
        'YTick', linspace(ylower, yupper, 11),...
        'YTickLabel', {num2str(ylower,4), '','','','',num2str((ylower + yupper)/2, 4),...
        '','','','',num2str(yupper,4)});
    set(data.handle.uicontrol(3), 'String', num2str((yupper-ylower)/10 ,3));
    data.autoset = 1;
    drawnow;
end

%% *******************************************************************
% Update the channel(s) that are being plotted.
function data = localChangeChannel(data)
%%
% Determine which channels are selected.
chan = get(data.handle.uicontrol(2), {'Value'});

%%
% Clean up the legend.
if strcmp(get(data.handle.menu(4),'Checked'),'off')
    set(data.handle.menu(4), 'Checked', 'On');
else
    set(data.handle.menu(4), 'Checked', 'Off');
end

%%
% If more than sixteen channels were selected, create a dialog which
% states only sixteen channels can be selected.
if length(chan{:}) > 16
    hWarn = findobj(findall(0), 'Tag', 'onlySixteenChannels');
    if isempty(hWarn)
        hWarn = warndlg('Only sixteen channels can be selected.','Data Acquisition Warning');
        set(hWarn, 'Tag', 'onlySixteenChannels');
    else
        figure(hWarn(1));
    end
    return;
else
    % Store the channels in the data structure.
    data.channel = chan{:};
    
    % Reset the legend
    data=localLegend(data);
end

%% *******************************************************************
% Stop the object and close the figure window.
function localClose(data)
%%
% Turn off Phasespace recording
putvalue(data.dio, 1);

%%
% Stop timer
stop(data.t);

if exist('SAVE_STATUS.mat', 'file')
    delete('SAVE_STATUS.mat');
end

%%
% Save the files if running and if recording
if data.state == 1 && data.numpoints == 1
    
    % Get all acquired data from data acquisition software
    [samples, time] = getdata(data.ai, get(data.ai, 'SamplesAvailable'));
    try
        samplesHandrail = getdata(data.ai2, get(data.ai2, 'SamplesAvailable'));
    catch e
        MCC_STATUS = 0;
    end
    realtime = data.checkpoints(1,:);
    
    % Get file name and save location
    SaveLocation = get(data.handle.uicontrol(1), 'String');
    filename = get(data.handle.uicontrol(4), 'String');
    
    % Calculate elapsed time and start/end indices for recorded data
    if ~isempty(data.checkpoints)
        c = clock;
        elapse(1,:) = c - data.checkpoints(1,:);
        
        elapse(6) = elapse(6) + elapse(3) * 86400;
        elapse(6) = elapse(6) + elapse(4) * 3600;
        elapse(6) = elapse(6) + elapse(5) * 60;
        elapse = elapse(6);
        
        starttime = time(end) - elapse;
        startpoint = length(time(time < starttime)) + 1;
        
        samples = samples(startpoint:end, :);
        time = time(startpoint:end, :);
        time = time - time(1,1);
        if ~exist('MCC_STATUS', 'var')
            samplesHandrail = samplesHandrail(startpoint:end, :);
        else
            samplesHandrail = 0;
        end
    end
    
    if get(data.handle.uicontrol(15), 'Value')
        maxTime = str2num(get(data.handle.uicontrol(16), 'String'));
        time = time(time <= maxTime);
        samples = samples(time <= maxTime, :);
        if ~exist('MCC_STATUS', 'var')
            samplesHandrail = samplesHandrail(time <= maxTime, :);
            if length(samplesHandrail) > length(samples)
                samplesHandrail = samplesHandrail(1:length(samples), :);
            end
        else
            samplesHandrail = 0;
        end
    end
    
    % Change to save location, save, then change back
    cd(SaveLocation);
    save(strcat(filename, '_', sprintf('%02d', data.trial)), 'samples',...
        'samplesHandrail', 'time', 'realtime');
    cd(get(data.ai, 'Tag'));
end

%%
% If no adaptors are registered, ai will be empty.
if ~isempty(data.ai)
    % Delete the object.
    delete(data.ai);
    if isempty(data.e)
        delete(data.ai2);
    end
end

%%
% Close the figure window.
delete(data.handle.figure);

%%
clc;

%% *******************************************************************
% Record time checkpoints
function data = localCheckpoint(data)
%%
% Get recording checkpoint if daq is running
if data.state == 1
    
    % Get current time
    c = clock;
    
    % Keep track of number of checkpoints
    numpoints = data.numpoints;
    numpoints = numpoints + 1;
    data.numpoints = numpoints;
    
    % Keep track of times of checkpoints
    checkpoints = data.checkpoints;
    checkpoints(data.numpoints, 1:6) = c(1:6);
    data.checkpoints = checkpoints;
    
    % Set the recording button text
    set(data.handle.uicontrol(14), 'String', 'Stop Recording');
    
    % Save if there are two checkpoints
    if numpoints == 2
        
        % Stop timer
        stop(data.t);
        
        % Get acquired data from the daq
        [samples, time] = getdata(data.ai, get(data.ai, 'SamplesAvailable'));
        try
            samplesHandrail = getdata(data.ai2, get(data.ai2, 'SamplesAvailable'));
        catch e
            MCC_STATUS = 0;
        end
        time = time - time(1,1);
        realtime = checkpoints(1,:);
        
        % Get file name and save location
        SaveLocation = get(data.handle.uicontrol(1), 'String');
        filename = get(data.handle.uicontrol(4), 'String');
        
        % Calculate elapsed time and start/end indices
        if ~isempty(checkpoints)
            elapse(1,:) = checkpoints(2,:) - checkpoints(1,:);
            
            elapse(6) = elapse(6) + elapse(3) * 86400;
            elapse(6) = elapse(6) + elapse(4) * 3600;
            elapse(6) = elapse(6) + elapse(5) * 60;
            elapse = elapse(6);
            
            starttime = time(end) - elapse;
            startpoint = length(time(time < starttime)) + 1;
            
            samples = samples(startpoint:end, :);
            time = time(startpoint:end, :);
            time = time - time(1,1);
            if ~exist('MCC_STATUS', 'var')
                samplesHandrail = samplesHandrail(startpoint:end, :);
            else
                samplesHandrail = 0;
            end
        end
        
        if get(data.handle.uicontrol(15), 'Value')
            maxTime = str2num(get(data.handle.uicontrol(16), 'String'));
            time = time(time <= maxTime);
            samples = samples(time <= maxTime, :);
            if ~exist('MCC_STATUS', 'var')
                samplesHandrail = samplesHandrail(time <= maxTime, :);
                if length(samplesHandrail) > length(samples)
                    samplesHandrail = samplesHandrail(1:length(samples), :);
                end
            else
                samplesHandrail = 0;
            end
            TIMED = 1;
        end
        
        % Change directory, save, then change back
        cd(SaveLocation);
        save(strcat(filename, '_', sprintf('%02d', data.trial)),...
            'samples', 'samplesHandrail', 'time', 'realtime');
        cd(get(data.ai, 'Tag'));
        
        % Increase trial number and reset checkpoints and GUI
        data.trial = data.trial + 1;
        data.numpoints = 0;
        data.checkpoints = [];
        set(data.handle.uicontrol(1), 'Enable', 'On');
        set(data.handle.uicontrol(4), 'Enable', 'On');
        set(data.handle.uicontrol(14), 'String', 'Record');
        set(data.handle.uicontrol(15), 'String', 'Timed Recording (sec)',...
            'Enable', 'on');
        if get(data.handle.uicontrol(15), 'Value')
            set(data.handle.uicontrol(16), 'Enable', 'on');
        end
        
        % Turn off phasespace recording
        putvalue(data.dio, 1);
        
        % Give a warning that recording is finished
        if exist('TIMED', 'var')
            warndlg('It''s done!', 'Ding!');
        end
        
    % Do if first checkpoint
    else
        set(data.handle.uicontrol(1), 'Enable', 'Off');
        set(data.handle.uicontrol(4), 'Enable', 'Off');
        
        % Set up timer and function
        data.t = timer('TimerFcn', 'SAVE_STATUS = 1; save(''SAVE_STATUS'', ''SAVE_STATUS'');',...
            'StartDelay', str2num(get(data.handle.uicontrol(16), 'String')),...
            'TasksToExecute', 1);
        
        % Do if timing checkbox is on
        if get(data.handle.uicontrol(15), 'Value')
            start(data.t);
            set(data.handle.uicontrol(15), 'String', 'Timing...');
            set(data.handle.uicontrol(16), 'Enable', 'off');
        end
        set(data.handle.uicontrol(15), 'Enable', 'off');
        
        % Turn on phasespace recording
        putvalue(data.dio, 0);
        
    end
end
%% *******************************************************************
% Help for the Data Acquisition Toolbox.
function localDaqHelp

doc('daq');

%% *******************************************************************
% Create a legend.
function data = localLegend(data)

if strcmp(get(data.handle.menu(4),'Checked'), 'off')  %isempty(data.handle.legend)
    
    if ~isempty(data.handle.line) && all(ishandle(data.handle.line))
        try
            % Make the axes visible.
            set(data.handle.axes, 'HandleVisibility', 'on');
            set(data.handle.figure, 'HandleVisibility', 'on');
            
            % Create the strings for the legend.
            names = get(data.handle.uicontrol(2), 'String');
            data.handle.legend = legend(data.handle.axes, data.handle.line(data.channel), names(data.channel, :));
            set(data.handle.legend,...
                'Color', [0 0.5 0.0],...
                'ButtonDownFcn', '',...
                'Interpreter', 'none');
            set(data.handle.menu(4), 'Checked', 'On');
            
            % So that the legend cannot be moved.
            set(get(data.handle.legend, 'Children'), ...
                'ButtonDownFcn', '');
            
            % Make the axes invisible.
            set(data.handle.axes, 'HandleVisibility', 'off');
            set(data.handle.figure, 'HandleVisibility', 'off');
        catch
            % Make the axes invisible.
            set(data.handle.axes, 'HandleVisibility', 'off');
            set(data.handle.figure, 'HandleVisibility', 'off');
        end
    else
        hWarn = findobj(findall(0), 'Tag', 'startForLegend');
        if isempty(hWarn)
            hWarn = warndlg('The analog input acquisition needs to be started.','Data Acquisition Warning');
            set(hWarn, 'Tag', 'startForLegend');
        else
            figure(hWarn(1));
        end
    end
else
    delete(data.handle.legend);
    data.handle.legend = [];
    set(data.handle.menu(4), 'Checked', 'Off');
end

%% *******************************************************************
% Help for the oscilloscope.
function localOsHelp

doc('daqscope');

%% *******************************************************************
% Initialize the object's properties and start the object.
function data = localStart(data)
%%
% Check for override
filename = get(data.handle.uicontrol(4), 'String');
SaveLocation = get(data.handle.uicontrol(1), 'String');
cd(SaveLocation);
check = size(dir([filename '*']),1);
MCC_ERROR = [];

%If there is already a file in the save directory, give a warning and reset
if check
    cd(get(data.ai, 'Tag'));
    warndlg('There is already a file with that name. Please choose another name.','File Name Warning');
    lastFilename =  get(data.ai, 'LogFileName');
    set(data.handle.uicontrol(4), 'String', lastFilename(1, 1:length(lastFilename) - 4));
    
    % If the data acquisition is already running, give a warning
elseif data.state == 1
    cd(get(data.ai, 'Tag'));
    warndlg('The data acquisition program is already running','Do Not Press While Running');
    
    %If okay, start the acquisition
else
    cd(get(data.ai, 'Tag'));
    % Initialize the axis according to current volots/div setting
    data=localVoltsRange(data);
    
    % Set the object to preview data only and plot every tenth of a second.
    set(data.ai,...
        'TriggerRepeat', 1,...
        'TriggerType', 'Manual',...
        'SamplesPerTrigger', Inf,...
        'TimerPeriod', 0.1,...
        'Timerfcn', @localTimerAction);
    if isempty(data.e) 
        set(data.ai2,...
            'TriggerRepeat', 1,...
            'TriggerType', 'Manual',...
            'SamplesPerTrigger', Inf,...
            'TimerPeriod', 0.1);
    else
        MCC_ERROR = 0;
    end
    
    % Add the correct channels based on the channels selected in the listbox.
    data = localChangeChannel(data);
    
    % Start the object and get the first samples.
    try
        start(data.ai)
        start(data.ai2)
    catch e
        if findstr('device winsound', lower(e.message))
            hWarn = findobj(findall(0), 'Tag', 'badSampleRateforDevice');
            if isempty(hWarn)
                warndlg(['The specified SampleRate is not supported for this soundcard''s',...
                    ' configuration.  Try specifying a new',...
                    ' SampleRate value.'], 'Data Acquisition error');
                set(hWarn, 'Tag', 'badSampleRateforDevice');
            else
                figure(hWarn(1));
            end
            return;
        elseif findstr('mcc: invalid board number', lower(e.message))
            MCC_STATUS = 0;
        elseif MCC_ERROR == 0
            MCC_STATUS = 0;
        else
            rethrow(e)
        end
    end
    
    set(data.handle.uicontrol(5), 'Enable', 'Off');
    set(data.handle.uicontrol(6), 'Enable', 'Off');
    
    trigger(data.ai)
    if ~exist('MCC_STATUS', 'var')
        trigger(data.ai2)
    end
    
    d1 = peekdata(data.ai, get(data.ai, 'SampleRate') * 5);
    
    if ~exist('MCC_STATUS', 'var') && data.bluebox
        d2 = peekdata(data.ai2, get(data.ai2, 'SampleRate') * 5);
        d = horzcat(d1, d2);
    else
        d = d1;
    end
    
    % If winsound object and channel 2 was only selected, plot only the
    % second column of data.
    if data.winsound2 && length(data.channel) == 1
        d = d(:,2);
    end
    
    % If the line exists, delete it - the line will exist if the object
    % was stopped and started.
    if ~isempty(data.handle.line)
        delete(data.handle.line);
        data.handle.line = [];
    end
    
    % Plot the first samples.
    hLine=[];
    
    for i = 1:size(d, 2)
        hLine(i) = line('Parent', data.handle.axes,...
            'Xdata', 1:(length(d(:,1))),...
            'Ydata', d(:,i),...
            'Color', data.map(i,:),...
            'HandleVisibility', 'off');
    end
    
    drawnow;
    
    % Store the new state.
    data.state = 1;
    
    % Store the handle to the lines in the data structure.
    data.handle.line = hLine;
    
end
%% *******************************************************************
% Stop the analog input object.
function data = localStop(data)

% stop object only if data.ai does exist
if isvalid(data.ai)
    
    % Get data if running
    if data.state == 1
        [samples, time] = getdata(data.ai, get(data.ai, 'SamplesAvailable'));
        try
            samplesHandrail = getdata(data.ai2, get(data.ai2, 'SamplesAvailable'));
        catch e
            MCC_STATUS = 0;
        end
    end
    
    % Stop the object if it exists and if it is running
    if ~isempty(data.ai) && (data.state ~= 0)
        stop(data.ai);
        if ~exist('MCC_STATUS', 'var') || exist('data.ai2')
            stop(data.ai2);
        end
        stop(data.t);
        
        % Turn off Phasespace recording
        putvalue(data.dio, 1);
    end
    
    % Store the new state.
    data.state = 0;
    
    %Enable changes in save directory and file name
    set(data.handle.uicontrol(1), 'Enable', 'On');
    set(data.handle.uicontrol(4), 'Enable', 'On');
    
    % Save the files if there is data and if recording started
    if exist('samples', 'var') && data.numpoints == 1
        
        % Get checkpoints
        checkpoints = data.checkpoints;
        realtime = checkpoints(1,:);
        
        % Get file name and save location
        SaveLocation = get(data.handle.uicontrol(1), 'String');
        filename = get(data.handle.uicontrol(4), 'String');
        
        % If recording already started, calculate elapsed time and
        % start/end indices
        if ~isempty(checkpoints)
            c = clock;
            elapse(1,:) = c - checkpoints(1,:);
            
            elapse(6) = elapse(6) + elapse(3) * 86400;
            elapse(6) = elapse(6) + elapse(4) * 3600;
            elapse(6) = elapse(6) + elapse(5) * 60;
            elapse = elapse(6);
            
            starttime = time(end) - elapse;
            startpoint = length(time(time < starttime)) + 1;
            
            samples = samples(startpoint:end, :);
            time = time(startpoint:end, :);
            time = time - time(1,1);
            if ~exist('MCC_STATUS', 'var')
                samplesHandrail = samplesHandrail(startpoint:end, :);
            else
                samplesHandrail = 0;
            end
        end
        
        if get(data.handle.uicontrol(15), 'Value')
            maxTime = str2num(get(data.handle.uicontrol(16), 'String'));
            time = time(time <= maxTime);
            samples = samples(time <= maxTime, :);
            if ~exist('MCC_STATUS', 'var')
                samplesHandrail = samplesHandrail(time <= maxTime, :);
                if length(samplesHandrail) > length(samples)
                    samplesHandrail = samplesHandrail(1:length(samples), :);
                end
            else
                samplesHandrail = 0;
            end
        end
        
        % Change directory, save, change back
        cd(SaveLocation);
        save(strcat(filename, '_', sprintf('%02d', data.trial)),...
            'samples', 'samplesHandrail', 'time', 'realtime');
        cd(get(data.ai, 'Tag'));
    end
    
    % Reset GUI and checkpoints
    set(data.handle.uicontrol(14), 'String', 'Record');
    data.trial = 1;
    data.checkpoints = [];
    data.numpoints = 0;
    
    % Delete functional file
    if exist('SAVE_STATUS.mat', 'file')
        delete('SAVE_STATUS.mat');
    end
    
    % Reset GUI
    set(data.handle.uicontrol(5), 'Enable', 'on');
    if get(data.handle.uicontrol(5), 'Value') == 1
        set(data.handle.uicontrol(6), 'Enable', 'on');
    end
    set(data.handle.uicontrol(15), 'String', 'Timed Recording (sec)',...
        'Enable', 'on');
    if get(data.handle.uicontrol(15), 'Value') == 1
        set(data.handle.uicontrol(16), 'Enable', 'on');
    end
end

%% *******************************************************************
% Continuously plot the data.
function data = localTimerAction(obj,event)
%%
% Get the data structure.
data = obj.UserData;
if isempty(data.e)
    obj2 = data.ai2;
end

% If the timer save status file exists, save the data
if exist('SAVE_STATUS.mat', 'file')
    delete('SAVE_STATUS.mat');
    treadmillForceData(data, gcbf, 'checkpoint');
end

if data.state == 1
    % Get the handles.
    hLine = data.handle.line;
    
    % Execute a peekdata.
    x1 = peekdata(obj, obj.SampleRate * 5);
    try
        x2 = peekdata(obj2, obj2.SampleRate * 5);
    catch e
        x2 = zeros(size(x1, 1), 6);
    end
    
    if isempty(x2)
        x2 = zeros(size(x1, 1), 6);
    end
    
    % Try combining the two data matrices together (fill difference in
    % dimensions with zeros)
    try
        x = horzcat(x1, x2);
    catch e
        diff = size(x2, 1) - size(x1, 1);
        more = zeros(diff, 14);
        x1 = vertcat(x1, more);
    end
    
    try
        x = horzcat(x1, x2);
    catch e
        diff = size(x1, 1) - size(x2, 1);
        more = zeros(diff, 6);
        x2 = vertcat(x2, more);
        x = horzcat(x1, x2);
    end
    
    % If winsound object and channel 2 was only selected, plot only the
    % second column of data.
    if data.winsound2 && length(data.channel) == 1
        x = x(:,2);
    end
    
    % Update the plot.
    set(hLine, 'Visible', 'Off');
    for i = data.channel
        set(hLine(i), 'Parent', data.handle.axes,...
            'Xdata', 1:(length(x(:,1))),...
            'YData', x(:,i),...
            'Color', data.map(i,:),...
            'Visible', 'On');
    end
    
    if data.autoset
        ymin = round(min(min(x(:, data.channel))) * 1000 - 1) / 1000;
        ymax = round(max(max(x(:, data.channel))) * 1000 + 1) / 1000;
        
        % If NaN's are returned base the limit off the other.
        if isnan(ymin) && isnan(ymax)
            ymin = -0.01;
            ymax = 0.01;
        elseif isnan(ymin)
            ymin = ymax - (abs(ymax)/2);
        elseif isnan(ymax)
            ymax = ymin + (abs(ymin)/2);
        end
        
        % Handle the case when the limits are equal.
        if ymin == ymax
            ymin = ymin - (abs(ymin)/2);
            ymax = ymax + (abs(ymax)/2);
        end
        
        % If they are still equal (if they both were zero).
        if ymin == ymax
            ymin = -0.01;
            ymax = 0.01;
        end
        
        set(data.handle.axes, 'YLim', [ymin, ymax],...
            'YTick', linspace(ymin, ymax, 11),...
            'YTickLabel', {num2str(ymin,4), '','','','',num2str((ymin + ymax)/2, 4),...
            '','','','',num2str(ymax,4)});
        set(data.handle.uicontrol(3), 'String', num2str((ymax-ymin)/10,3));
    end
    
    sampleRate = get(data.ai, 'SampleRate');
    range = floor(sampleRate*5);
    
    c = clock;
    currentTime = datestr(c, 'HH:MM:SS');
    c(6) = c(6) - 5;
    beforeTime = datestr(c, 'HH:MM:SS');
    
    % Update the axes to range from 5 sec before to present.
    set(data.handle.axes,...
        'XLim'              ,[0 range]                              ,...
        'XTick'             ,linspace(0,range,11)                    ,...
        'XTickLabel'        ,{beforeTime,'','','','','','','','','',currentTime});
end

drawnow;

%% *******************************************************************
% Update the axes range and slider range.
function localUpdateRanges(data)

% ai doesn't exist if no adaptors are registered.
if ~isempty(data.ai)
    
    sampleRate = get(data.ai, 'SampleRate');
    range = floor(sampleRate*5);
    
    c = clock;
    currentTime = datestr(c, 'HH:MM:SS');
    c(6) = c(6) - 5;
    beforeTime = datestr(c, 'HH:MM:SS');
    
    % Update the axes to range from 5 sec before to present.
    set(data.handle.axes,...
        'XLim'              ,[0 range]                              ,...
        'XTick'             ,linspace(0,range,11)                    ,...
        'XTickLabel'        ,{beforeTime,'','','','','','','','','',currentTime});
    
    % initialize the axis according to current volots/div setting
    data=localVoltsRange(data);
end

%% *******************************************************************
% Update save file name.
function data = localFileName(data)
%%
% Get the file name.
filename = get(data.handle.uicontrol(4), 'String');

%%
% Check for override
SaveLocation = get(data.handle.uicontrol(1), 'String');
cd(SaveLocation);
check = size(dir([filename '*']),1);

if check
    warndlg('There is already a file with that name. Please choose another name.','File Name Warning');
    lastFilename =  get(data.ai, 'LogFileName');
    set(data.handle.uicontrol(4), 'String', lastFilename(1, 1:length(lastFilename) - 4));
    
else
    data.trial = 1;
end

cd(get(data.ai, 'Tag'));

%% *******************************************************************
% Change save location
function data = localSaveLocation(data)
%%
% Get new directory
SaveLocation = uigetdir;

%%
% Make it the new directory
set(data.handle.uicontrol(1), 'String', SaveLocation);

%% *******************************************************************
% Allow the volts per division to be specified.
function data = localVoltsCheck(data)
%%
% Turn on the volts/div radiobutton.
set(data.handle.uicontrol(8), 'Value', 1);
set(data.handle.uicontrol(3), 'Enable', 'on');

%%
% Turn off the autoset radiobutton.
set(data.handle.uicontrol(7), 'Value', 0);

%%
% Update the data structure.
data.autoset = 0;

%% *******************************************************************
% Update the y-axis range.
function data = localVoltsRange(data)
%%
% Get the value of the edit text box.
val = str2num(get(data.handle.uicontrol(3), 'String'));

if val <= 0
    hWarn = findobj(findall(0), 'Tag', 'voltsperdivision');
    if isempty(hWarn)
        hWarn = warndlg('Volts per division must be a positive number.','Data Acquisition Warning');
        set(hWarn, 'Tag', 'voltsperdivision');
    else
        figure(hWarn(1));
    end
    return;
end

%%
% Set the y-axis limits.
midYLim = 0;
yupper = 5*val+midYLim;
ylower = (-5*val)+midYLim;
set(data.handle.axes,...
    'YLim', [ylower yupper],...
    'YTick', linspace(ylower, yupper, 11),...
    'YTickLabel', {num2str(ylower,4), '','','','',num2str((ylower + yupper)/2, 4),...
    '','','','',num2str(yupper,4)});

%% *******************************************************************
% Allow users to modify sampleRate.
function data = localCheckBox(data)

switch get(data.handle.uicontrol(5), 'Value')
    case 0
        set(data.handle.uicontrol(6),...
            'Enable', 'off');
    case 1
        set(data.handle.uicontrol(6),...
            'Enable', 'on');
end

%% *******************************************************************
% Allow users to modify timer.
function data = localCheckBoxTimer(data)

switch get(data.handle.uicontrol(15), 'Value')
    case 0
        set(data.handle.uicontrol(16),...
            'Enable', 'off');
    case 1
        set(data.handle.uicontrol(16),...
            'Enable', 'on');
end

%% *******************************************************************
% Change the sampleRate.
function data = localSampleRate(data)

sampleRate = str2num(get(data.handle.uicontrol(6), 'String'));

switch data.state
    case 1
        try
            data = localStop(data);
            set(data.ai, 'SampleRate', sampleRate);
            %data = localStart(data);
        catch e
            rethrow(e);
        end
        
    otherwise
        try
            data = localStop(data);
            set(data.ai, 'SampleRate', sampleRate);
            set(data.ai2, 'SampleRate', sampleRate);
            %data = localStart(data);
        catch e
            rethrow(e);
        end       
end

localUpdateRanges(data)

%% *******************************************************************
% Initialize the scope window.
function data = localInitFig(data)
%%
% Initialize variables.
fgColor=get(0,'DefaultUIControlForegroundColor');
bgColor=get(0,'DefaultUIControlBackgroundColor');

%%
% Position the GUI in the middle of the screen
screenUnits=get(0,'Units');
set(0,'Units','pixels');
screenSize=get(0,'ScreenSize');
set(0,'Units',screenUnits);

XOffset=15;
figWidth=580+XOffset;

YOffset=0;
figHeight=335;

figPos=[(screenSize(3)-figWidth)/2 (screenSize(4)-figHeight)/2  ...
    figWidth                    figHeight];

%%
% Information for all handle graphics objects.m
genInfo.HandleVisibility='off';
genInfo.Interruptible='off';
genInfo.BusyAction='queue';

%%
% Create the figure window.
hFig=figure(genInfo,...
    'Color'             ,[0 0 0]                   ,...
    'DeleteFcn'         ,'treadmillForceData(''close'', gcbf)',...
    'DoubleBuffer'      ,'on'                        ,...
    'IntegerHandle'     ,'off'                       ,...
    'MenuBar'           ,'none'                      ,...
    'Name'              ,'Treadmill Force Data'      ,...
    'Tag'               ,'Voltmeter'                 ,...
    'NumberTitle'       ,'off'                       ,...
    'Units'             ,'pixels'                    ,...
    'Position'          ,[7 50 1265 925]                      ,...
    'Resize'            ,'off'                        ,...
    'UserData'          ,[]                          ,...
    'Colormap'          ,[]                          ,...
    'Pointer'           ,'arrow'                     ,...
    'Visible'           ,'off'                        ...
    );

genInfo.Parent = hFig;

%%
% Information for all uicontrols.
uiInfo=genInfo;
uiInfo.BackGroundColor=bgColor;
uiInfo.ForeGroundColor=fgColor;

%%
% Create the axes.
axPos = [46+XOffset 26+YOffset 950 750];

scopeMap = [1.0000    1.0000         0;
    1.0000    1.0000    1.0000;
    1.0000    0.1000         0;
         0         0    1.0000;
         0    1.0000    1.0000;
    0.3000    0.2500    0.7000;
    1.0000    0.6000    0.2000;
    0.9000    0.1000    0.7000;
    0.2000    0.8000    1.0000;
    0.5000    0.2500    0.5000;
    1.0000    0.8000    0.8000;
    0.7333    0.2667    1.0000;
    0.4000         0         0;
    0.8000    0.4000    0.2000;
    0.5000    0.7500    1.0000;
    1.0000    0.4000    0.2000;
    0.6777    0.2500    0.1000;
    0.1000    1.0000    0.7500;
    1.0000    0.2500    1.0000;
    0.8500         0    1.0000];

hAxes = axes(genInfo,...
    'Units'             ,'pixels'                   ,...
    'Position'          ,axPos                      ,...
    'Box'               ,'On'                       ,...
    'TickLength'        ,[0 0]                      ,...
    'DrawMode'          ,'fast'                     ,...
    'Color'             ,[0 0 0]                ,...
    'ColorOrder'        ,scopeMap                   ,...
    'XLim'              ,[0 512]                    ,...
    'XTick'             ,linspace(0,512,11)         ,...
    'XColor'            ,[1 1 1]                    ,...
    'XTickLabel'        ,{'0','','','','','','','','','','800'},...
    'YLim'              ,[-1 1]                     ,...
    'YTick'             ,linspace(-1,1,11)          ,...
    'YColor'            ,[1 1 1]                   ,...
    'YTickLabel'        ,{'-1','','','','','','','','','','1'},...
    'XGrid'             ,'on'                       ,...
    'YGrid'             ,'on'                       ,...
    'GridLineStyle'     ,':');

%%
% Create the frames.
framePos = {[1000+XOffset 26+YOffset 220 750], [1005+XOffset 255 200 60]};

for i = 1:length(framePos)
    hFrame = uicontrol(uiInfo,...
        'Style'          , 'frame'     ,...
        'Units'          , 'pixels'    ,...
        'Position'       , framePos{i});
end

%%
% Get adaptor information:
% adaptorStr = list of adaptors for the popup = {'winsound0' 'nidaq1'}.
% ai = analoginput object constructed from adaptorStr{1}.
% names = corresponding channel names to ai.

%[adaptorStr, ai, names] = daqgate('privateGetAdaptor', 'analoginput');
ai = analoginput('nidaq', 'Dev1');

set(ai,...
    'InputType', 'SingleEnded',...
    'TriggerRepeat', 1,...
    'TriggerType', 'Manual',...
    'SampleRate', 960,...
    'SamplesPerTrigger', Inf,...
    'TimerPeriod', 0.1,...
    'Timerfcn', @localTimerAction,...
    'Tag', cd);

addchannel(ai, 0:13);

BlueBox = 0; %if use bluebox (FS1208), use 1; else, use 0;

% if ~BlueBox
%     addchannel(ai, 66:71); %Handrail Channel
% end

if ~BlueBox
    addchannel(ai, [17 18 19 20 29 31]); %Handrail Channel
end

e = [];


try
    ai2 = analoginput('mcc', 0); %1); %
catch board
    if findstr('mcc: invalid board number', lower(board.message))
        ai2 = analoginput('mcc', 1);
    end
end
    
try
    set(ai2,...
        'InputType', 'SingleEnded',...
        'TriggerRepeat', 1,...
        'TriggerType', 'Manual',...
        'SampleRate', 960,...
        'SamplesPerTrigger', Inf,...
        'TimerPeriod', 0.1,...
        'Tag', cd);

    addchannel(ai2, 0:5);
  



catch e
end

dio = digitalio('nidaq', 'Dev1');
addline(dio, 0:1, 'Out');

% Description of data.handle.uicontrol:
% 1: file save directory
% 2: listbox
% 3: edit text box - Volts\Div
% 4: edit text box - Filename
% 5: checkbox - SampleRate
% 6: edit text box - SampleRate
% 7: radiobutton - Autoset
% 8: text label - Volts/Div
% 9: button - Play
%10: button - Stop
%11: button - Get File Directory
%12: edit text box - File Directory
%13: text label - Filename
%14: button - Record
%15: checkbox - Timer
%16: edit text box - Timer
%17: text label - Display Channel
%18: text label - Y-Axis

%%
% Label the file directory textbox.
textPos = [1005+XOffset 690+YOffset 124 20];

h(12) = uicontrol(uiInfo,...
    'Style'                ,'text'                ,...
    'String'               ,'Save To:'            ,...
    'HorizontalAlignment'  ,'left'                ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,textPos);

%%
% Create the textbox with the save directory
savePos = [1005+XOffset 675+YOffset 185 20];

h(1) = uicontrol(uiInfo,...
    'BackgroundColor'      ,1-fgColor ,...
    'Style'                ,'edit'      ,...
    'String'               ,char(cd)    ,...
    'Units'                ,'pixels'    ,...
    'Position'             , savePos  ,...
    'HorizontalAlignment'  ,'left');

%%
% Label channel display list
textPos = [1005+XOffset 645+YOffset 124 20];

h(17) = uicontrol(uiInfo,...
    'Style'                ,'text'                ,...
    'String'               ,'Display Channel:'    ,...
    'HorizontalAlignment'  ,'left'                ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,textPos);

%%
% Create the channel listbox.
listPos = [1035+XOffset 412+YOffset 138 236];

h(2) = uicontrol(uiInfo,...
    'BackgroundColor' ,1-fgColor,...
    'Style'           ,'listbox'        ,...
    'Max'             ,3                ,...
    'Min'             ,1                ,...
    'Units'           ,'pixels'         ,...
    'Position'        ,listPos          ,...
    'String'          ,['Fx_Left  '; 'Fy_Left  '; 'Fz_Left  '; 'Mx_Left  ';...
                        'My_Left  '; 'Mz_Left  '; 'Channel6 '; 'Channel7 ';...
                        'Fx_Right '; 'Fy_Right '; 'Fz_Right '; 'Mx_Right ';...
                        'My_Right '; 'Mz_Right '; 'HR_F1    '; 'HR_F2    ';...
                        'HR_F3    '; 'HR_M1    '; 'HR_M2    '; 'HR_M3    '],... 
    'Callback'        ,'treadmillForceData(''changeChannel'', gcbf);');

%%
% Label y-axis editing buttons
textPos = [1005+XOffset 315+YOffset 124 20];

h(18) = uicontrol(uiInfo,...
    'Style'                ,'text'                ,...
    'String'               ,'Y-Axis:'    ,...
    'HorizontalAlignment'  ,'left'                ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,textPos);

%%
% Create the edit text box - Volts/Div.
EditPos = [1125+XOffset 290+YOffset 60 20];

h(3) = uicontrol(uiInfo,...
    'BackgroundColor'      ,1-fgColor ,...
    'Style'                ,'edit'      ,...
    'String'               ,'0.3'       ,...
    'Units'                ,'pixels'    ,...
    'Position'             , EditPos  ,...
    'HorizontalAlignment'  ,'left'      ,...
    'Callback'             ,'treadmillForceData(''voltsrange'', gcbf);');

%%
% Label the radiobutton - Volts/Div.
textPos = [1010+XOffset 290+YOffset 100 20];

h(8) = uicontrol(uiInfo,...
    'Style'                ,'radiobutton' ,...
    'Value'                ,1             ,...
    'String'               ,'Volts/Division'   ,...
    'HorizontalAlignment'  ,'left'        ,...
    'Units'                ,'pixels'      ,...
    'Position'             ,textPos       ,...
    'Callback'             ,'treadmillForceData(''voltscheck'', gcbf);');

%%
% Label the file name textbox.
textPos = [1005+XOffset 735+YOffset 124 20];

h(13) = uicontrol(uiInfo,...
    'Style'                ,'text'                ,...
    'String'               ,'File Name:'        ,...
    'HorizontalAlignment'  ,'left'                ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,textPos);

%%
% Create the textbox with the file name inside.
filePos = [1005+XOffset 720+YOffset 185 20];

h(4) = uicontrol(uiInfo,...
    'BackgroundColor'      ,1-fgColor ,...
    'Style'                ,'edit'      ,...
    'String'               ,'logfile'       ,...
    'Units'                ,'pixels'    ,...
    'Position'             , filePos  ,...
    'HorizontalAlignment'  ,'left'      ,...
    'Callback'             ,'treadmillForceData(''filename'', gcbf);');

%%
% Create the SampleRate checkbox.
CheckBoxPos=[1010+XOffset 345+YOffset 100 20];

h(5) = uicontrol(uiInfo,...
    'Style'                ,'checkbox'            ,...
    'Value'                ,0                     ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,CheckBoxPos           ,...
    'String'               ,'SampleRate/Sec'      ,...
    'HorizontalAlignment'  ,'left'                ,...
    'Callback'             ,'treadmillForceData(''checkbox'', gcbf);');

%%
% Create the SampleRate edit text box.
sampleRate = get(ai, 'SampleRate');
EditPos=[1145+XOffset 345+YOffset 60 20];

h(6) = uicontrol(uiInfo,...
    'BackgroundColor'      ,1-fgColor,...
    'Style'                ,'edit'                ,...
    'Enable'               ,'off'                 ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,EditPos               ,...
    'String'               ,num2str(sampleRate)   ,...
    'HorizontalAlignment'  ,'left'                ,...
    'Callback'             ,'treadmillForceData(''sampleRate'', gcbf);');

%%
% Create the timer checkbox.
CheckBoxTimerPos=[1010+XOffset 375+YOffset 130 20];

h(15) = uicontrol(uiInfo,...
    'Style'                ,'checkbox'            ,...
    'Value'                ,0                     ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,CheckBoxTimerPos      ,...
    'String'               ,'Timed Recording (sec)'     ,...
    'HorizontalAlignment'  ,'left'                ,...
    'Callback'             ,'treadmillForceData(''checkboxtimer'', gcbf);');

%%
% Create the timer edit text box.
EditTimerPos=[1145+XOffset 375+YOffset 60 20];

h(16) = uicontrol(uiInfo,...
    'BackgroundColor'      ,1-fgColor,...
    'Style'                ,'edit'                ,...
    'Enable'               ,'off'                 ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,EditTimerPos          ,...
    'String'               ,60   ,...
    'HorizontalAlignment'  ,'left');

%%
% Create the autoset radiobutton.
RadioPos=[1010+XOffset 260+YOffset 124 20];

h(7) = uicontrol(uiInfo,...
    'Style'                ,'radiobutton'         ,...
    'Value'                ,0                     ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,RadioPos              ,...
    'String'               ,'Autoset Y-Axis'      ,...
    'Callback'             ,'treadmillForceData(''autoset'', gcbf);');

%%
% Create the stop CData.
square = ones(16,16,3);
square(:,:,1)=bgColor(1);
square(:,:,2)=bgColor(2);
square(:,:,3)=bgColor(3);
square(4:12, 4:12, 1) = fgColor(1);
square(4:12, 4:12, 2) = fgColor(2);
square(4:12, 4:12, 3) = fgColor(3);

%%
% Create the start CData.
triangle = ones(16,16,3);
triangle(:,:,1)=bgColor(1);
triangle(:,:,2)=bgColor(2);
triangle(:,:,3)=bgColor(3);
%*bgColor(1);
for i = 1:5
    for j = 1:2
        triangle(3+i:13-i,3+i+j,1)=fgColor(1);
        triangle(3+i:13-i,3+i+j,2)=fgColor(2);
        triangle(3+i:13-i,3+i+j,3)=fgColor(3);
    end
end

%%
%Create folder location button
dots = ones(16,16,3);
dots(:,:,1)=bgColor(1);
dots(:,:,2)=bgColor(2);
dots(:,:,3)=bgColor(3);
dots(11:12, 4:5, 1) = fgColor(1);
dots(11:12, 4:5, 2) = fgColor(2);
dots(11:12, 4:5, 3) = fgColor(3);
dots(11:12, 7:8, 1) = fgColor(1);
dots(11:12, 7:8, 2) = fgColor(2);
dots(11:12, 7:8, 3) = fgColor(3);
dots(11:12, 10:11, 1) = fgColor(1);
dots(11:12, 10:11, 2) = fgColor(2);
dots(11:12, 10:11, 3) = fgColor(3);

%%
% Create the play button.
h(9) = uicontrol(uiInfo,...
    'Style'                ,'pushbutton'         ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,[8 825 40 40]              ,...
    'CData'                ,triangle               ,...
    'TooltipString'        ,'Start Acquisition'    ,...
    'Callback'             ,'treadmillForceData(''start'',gcbf);');

%%
%Create the stop bar
h(10) = uicontrol(uiInfo,...
    'Style'                ,'pushbutton'         ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,[58 825 40 40]              ,...
    'Cdata'                ,square                ,...
    'TooltipString'        ,'Stop Acquisition'    ,...
    'Callback'             ,'treadmillForceData(''stop'', gcbf);');

%%
%Create the get directory button
h(11) = uicontrol(uiInfo,...
    'Style'                ,'pushbutton'         ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,[1210 675 20 20]              ,...
    'CData'                ,dots       ,...
    'TooltipString'        ,'Select File Save Location'    ,...
    'Callback'             ,'treadmillForceData(''savelocation'',gcbf);');

%%
%Create start/stop point button
h(14) = uicontrol(uiInfo,...
    'Style'                ,'pushbutton'         ,...
    'Units'                ,'pixels'              ,...
    'Position'             ,[108 825 160 40]              ,...
    'String'               ,'Record'         ,...
    'FontSize'             ,16                   ,...
    'TooltipString'        ,'Start/Stop Recording'    ,...
    'Callback'             ,'treadmillForceData(''checkpoint'', gcbf);');

%%
% Create the File menu.
menu(1) = uimenu('Label', 'File',...
    'ForegroundColor',fgColor,...
    'Parent'             ,hFig);
menu(2) = uimenu(menu(1),...
    'ForegroundColor',fgColor,...
    'Label'              ,'Close Oscilloscope'      ,...
    'Callback'           ,'treadmillForceData(''close'', gcbf);');

%%
% Create the View menu.
menu(3) = uimenu('Label', 'View',...
    'ForegroundColor',fgColor,...
    'Parent'             ,hFig);
menu(4) = uimenu(menu(3),...
    'ForegroundColor',fgColor,...
    'Label'              ,'Legend'                  ,...
    'Callback'           ,'treadmillForceData(''legend'',gcbf);');

%%
% Create the help menu.
menu(5) = uimenu('Label', 'Help',...
    'ForegroundColor',fgColor,...
    'Parent'             ,hFig);
menu(6) = uimenu(menu(5),...
    'ForegroundColor',fgColor,...
    'Label'              ,'Oscilloscope Help'     ,...
    'Callback'           ,'treadmillForceData(''oshelp'', gcbf);');
menu(7) = uimenu(menu(5),...
    'ForegroundColor',fgColor,...
    'Label'              ,'Data Acquisition Help' ,...
    'Callback'           ,'treadmillForceData(''daqhelp'', gcbf);');

%%
% Create the data structure.
data.handle.figure = hFig;
data.handle.axes = hAxes;
data.handle.uicontrol = h;
data.handle.line = [];

data.handle.menu = menu;
data.handle.legend = [];
data.ai = ai;
data.dio = dio;
data.channel = 1;
data.cdata = triangle;
data.map = scopeMap;
data.state = 0;
data.winsound2 = 0;
data.autoset = 0;
data.trial = 1;
data.checkpoints = [];
data.numpoints = 0;
data.t = timer;
data.e = e;
if isempty(e)
    data.ai2 = ai2;
end
data.bluebox = BlueBox;

%%
% Set the axes limits to be from 0 to the SampleRate.
localUpdateRanges(data)

%%
% Store the data structure and display figure.
set(hFig,'Visible','on','UserData',data);

%%
% Store the data structure in the object.
set(data.ai, 'UserData', data);
if isempty(e)
    set(data.ai2, 'UserData', data);
end
