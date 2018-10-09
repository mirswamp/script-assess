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
    public class XmlLogger : Logger
    {
        private XmlWriter xmlWriter;
        private string DOTNET_HOST_PATH;

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

            try
            {
                XmlWriterSettings settings = new XmlWriterSettings();
                settings.Encoding = Encoding.UTF8;
                settings.Indent = true;
                settings.IndentChars = ("    ");
                // Open the file
                this.xmlWriter = XmlWriter.Create(logFile, settings);
            } catch (Exception ex)
            {
                if
                (
                 ex is UnauthorizedAccessException
                 || ex is ArgumentNullException
                 || ex is PathTooLongException
                 || ex is DirectoryNotFoundException
                 || ex is NotSupportedException
                 || ex is ArgumentException
                 || ex is SecurityException
                 || ex is IOException
                 )
                {
                    throw new LoggerException("Failed to create log file: " + ex.Message);
                }
                else
                {
                    // Unexpected failure
                    throw;
                }
            }

            this.xmlWriter.WriteStartDocument();
            this.xmlWriter.WriteStartElement("build-artifacts");
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

                    if (DOTNET_HOST_PATH == null)
                    {
                        throw new LoggerException("Did not find DOTNET_HOST_PATH env variable");
                    }

                    if (!cli_event.CommandLine.StartsWith(DOTNET_HOST_PATH))
                    {
                        return;
                    }

                   

                    this.xmlWriter.WriteStartElement("dotnet-compile");
                    this.xmlWriter.WriteAttributeString("sender", cli_event.SenderName);
                    this.xmlWriter.WriteAttributeString("code", cli_event.Code);
                    this.xmlWriter.WriteAttributeString("sub-type", cli_event.Subcategory);

                    WriteString("project-file", cli_event.ProjectFile);
                    string command_line = cli_event.CommandLine;
                    WriteString("command-blob", command_line);
                    WriteString("executable", DOTNET_HOST_PATH);

                    command_line = command_line.Substring(DOTNET_HOST_PATH.Length).Trim();

                    ArrayList flags = new ArrayList();
                    ArrayList classpath = new ArrayList();
                    ArrayList srcfiles = new ArrayList();
                    ArrayList analyzers = new ArrayList();
                    ArrayList libs = new ArrayList();

                    // First argument after the dotnet.exe is the compiler.dll, add that to lib
                    Regex regex = new Regex(@"(\/[\w]+:\x22[^\x22]+\x22|\/\w+:[^\s]+|\x22[^\x22]+\x22|[^\s]+)");
                    Regex compiler_lib = new Regex(@"(\x22[^\x22]+[.]dll\x22|[^\s]+[.]dll)");

                    if (compiler_lib.IsMatch(command_line))
                    {
                        Match match = compiler_lib.Match(command_line);

                        libs.Add(RemoveQuotes(match.Value));
                        command_line = command_line.Substring(match.Value.Length).Trim();
                    }

                    //Regex msbuild_option = new Regex(@"(\/[\w]+:\x22[^\x22]+\x22|\/\w+:[^\s]+)");
                    Regex srcfile_regex = new Regex(@"(\x22.+[.](cs|vb|fs)\x22|.+[.](cs|vb|fs)$)");

                    foreach (String match in regex.Split(command_line))
                    {

                        String arg = match;
                        arg = arg.Trim();

                        if (arg.Length == 0)
                        {
                            continue;
                        }

                        if (arg.StartsWith("/reference:"))
                        {
                            classpath.Add(Trim(arg.Substring("/reference:".Length)));
                        }
                        else if (arg.StartsWith("/analyzer:"))
                        {
                            analyzers.Add(Trim(arg.Substring("/analyzer:".Length)));
                        }
                        else if (arg.StartsWith("/resource:"))
                        {
                            flags.Add(arg);
                        }
                        else if (srcfile_regex.IsMatch(arg))
                        {
                            srcfiles.Add(Trim(arg));
                        }
                        else
                        {
                            flags.Add(arg);
                        }
                    }

                    WriteList("flags", "flag", flags);
                    WriteList("classpath", "file", classpath);
                    WriteList("analyzers", "file", analyzers);
                    WriteList("srcfile", "file", srcfiles);
                    WriteList("library", "file", libs);
                    this.xmlWriter.WriteEndElement();
                }
            }
        }

        void eventSource_TaskStarted(object sender, TaskStartedEventArgs e)
        {
            
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
                    //Console.WriteLine("{0}: {1}", (String)curr.Key, (String)curr.Value);
                    if (((String)curr.Key).Equals("DOTNET_HOST_PATH"))
                    {
                        DOTNET_HOST_PATH = (String)curr.Value;
                        break;
                    }
                }
            }

        }

        void eventSource_ProjectFinished(object sender, ProjectFinishedEventArgs e)
        {

        }

        void WriteList(String head_tag, String elem_tag, ArrayList array_list)
        {
            if (array_list.Count == 0)
            {
                return;
            }
            this.xmlWriter.WriteStartElement(head_tag);
            foreach (String elem in array_list)
            {
                this.xmlWriter.WriteStartElement(elem_tag);
                this.xmlWriter.WriteCData(elem);
                this.xmlWriter.WriteEndElement();
            }
            this.xmlWriter.WriteEndElement();
        }


        void WriteString(String tag, String data)
        {
            this.xmlWriter.WriteStartElement(tag);
            this.xmlWriter.WriteCData(data);
            this.xmlWriter.WriteEndElement();
        }

        void WriteString(String tag, IDictionary<string, string> attrs, String data)
        {
            this.xmlWriter.WriteStartElement(tag);

            foreach (KeyValuePair<string, string> item in attrs)
            {
                this.xmlWriter.WriteAttributeString(item.Key, item.Value);
            }
            this.xmlWriter.WriteCData(data);
            this.xmlWriter.WriteEndElement();
        }

        string Trim (string instr)
        {
            char[] charsToTrim = { '"',  ' ' };
            return instr.Trim(charsToTrim);
        }

        string RemoveQuotes(string str)
        {
            if (str.StartsWith("\"") && str.EndsWith("\""))
            {
                char[] charsToTrim = { '"'};
                return str.Trim(charsToTrim);
            }else
            {
                return str;
            }
        }

        /// <summary>
        /// Shutdown() is guaranteed to be called by MSBuild at the end of the build, after all 
        /// events have been raised.
        /// </summary>
        public override void Shutdown()
        {
            // Done logging, let go of the file
            this.xmlWriter.WriteEndElement();
            this.xmlWriter.WriteEndDocument();
            xmlWriter.Close();
        }

        void WriteConsole(String tag, String data)
        {
            Console.WriteLine("{0} :: {1}", tag, data);
        }

    }
}

