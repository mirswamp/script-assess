using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Security;
using Microsoft.Build.Framework;
using Microsoft.Build.Utilities;
using System.Xml;
using System.Text;
using System.Text.RegularExpressions;


namespace SwampBuildMonitor
{
    // This logger will derive from the Microsoft.Build.Utilities.Logger class,
    // which provides it with getters and setters for Verbosity and Parameters,
    // and a default empty Shutdown() implementation.
    public class TextLogger : Logger
    {
 
        public override void Initialize(IEventSource eventSource)
        {
            // The name of the log file should be passed as the first item in the
            // "parameters" specification in the /logger switch.  It is required
            // to pass a log file to this logger. Other loggers may have zero or more than 
            // one parameters.
            if (null == Parameters)
            {
                throw new LoggerException("Log file was not set.");
            }
            string[] parameters = Parameters.Split(';');

            string logFile = parameters[0];
            if (String.IsNullOrEmpty(logFile))
            {
                throw new LoggerException("Log file was not set.");
            }

            if (parameters.Length > 1)
            {
                throw new LoggerException("Too many parameters passed.");
            }

            // For brevity, we'll only register for certain event types. Loggers can also
            // register to handle TargetStarted/Finished and other events.
            eventSource.ProjectStarted += new ProjectStartedEventHandler(eventSource_ProjectStarted);
            eventSource.ProjectFinished += new ProjectFinishedEventHandler(eventSource_ProjectFinished);
            eventSource.TaskStarted += new TaskStartedEventHandler(eventSource_TaskStarted);
            eventSource.TaskFinished += new TaskFinishedEventHandler(eventSource_TaskFinished);
            eventSource.MessageRaised += new BuildMessageEventHandler(eventSource_MessageRaised);
            eventSource.WarningRaised += new BuildWarningEventHandler(eventSource_WarningRaised);
            eventSource.ErrorRaised += new BuildErrorEventHandler(eventSource_ErrorRaised);
        }

        void eventSource_ErrorRaised(object sender, BuildErrorEventArgs e)
        {
            // BuildErrorEventArgs adds LineNumber, ColumnNumber, File, amongst other parameters
        }

        void eventSource_WarningRaised(object sender, BuildWarningEventArgs e)
        {
            // BuildWarningEventArgs adds LineNumber, ColumnNumber, File, amongst other parameters
        }


        void eventSource_MessageRaised(object sender, BuildMessageEventArgs e)
        {
            // BuildMessageEventArgs adds Importance to BuildEventArgs
            // Let's take account of the verbosity setting we've been passed in deciding whether to log the message
            if ((e.Importance == MessageImportance.High && IsVerbosityAtLeast(LoggerVerbosity.Minimal))
            || (e.Importance == MessageImportance.Normal && IsVerbosityAtLeast(LoggerVerbosity.Normal))
            || (e.Importance == MessageImportance.Low && IsVerbosityAtLeast(LoggerVerbosity.Detailed))
            )
            {

                if (e.GetType().FullName == "Microsoft.Build.Framework.TaskCommandLineEventArgs")
                {

                    TaskCommandLineEventArgs cli_event = (TaskCommandLineEventArgs)e;
                    
                    WriteString("PROJECT FILE", cli_event.ProjectFile);
                    WriteString("COMMAND BLOB", cli_event.CommandLine);
                    WriteString("SUB CATEGORY", cli_event.Subcategory);
                    WriteString("TASKNAME", cli_event.TaskName);
                    WriteString("FILE", cli_event.File);
                    WriteString("CODE", cli_event.Code);
                }
            }
        }

        void eventSource_TaskStarted(object sender, TaskStartedEventArgs e)
        {
           /* WriteString("TaskStartedEventArgs.GetType().FullName", e.GetType().FullName);
            WriteString("TaskStartedEventArgs.TaskFile", e.TaskFile);
            WriteString("TaskStartedEventArgs.TaskName", e.TaskName);
            WriteString("TaskStartedEventArgs.Message", e.Message);
            WriteString("TaskStartedEventArgs.ProjectFile", e.ProjectFile);
            */
        }

        void eventSource_TaskFinished(object sender, TaskFinishedEventArgs e)
        {

        }

        void eventSource_ProjectStarted(object sender, ProjectStartedEventArgs e)
        {

            // ProjectStartedEventArgs adds ProjectFile, TargetNames
            // Just the regular message string is good enough here, so just display that.
            // DOTNET_HOST_PATH

            IEnumerable<DictionaryEntry> e2 = (IEnumerable<DictionaryEntry>)e.Properties;
            if (e2 != null)
            {
                IEnumerator ei = e2.GetEnumerator();
                while (ei.MoveNext())
                {
                    DictionaryEntry curr = (DictionaryEntry)ei.Current;
                    WriteString((String)curr.Key, (String)curr.Value);
                }
            }

        }

        void eventSource_ProjectFinished(object sender, ProjectFinishedEventArgs e)
        {

        }

        void WriteString(String tag, String data)
        {
            Console.WriteLine("{0} :: {1}", tag, data);
        }


        /// <summary>
        /// Shutdown() is guaranteed to be called by MSBuild at the end of the build, after all 
        /// events have been raised.
        /// </summary>
        public override void Shutdown()
        {
            // Done logging, let go of the file
        }


    }
}
