-- send_mail.applescript
-- Send email via macOS Mail.app
-- Usage: osascript send_mail.applescript "to@email.com" "Subject" "Body text" ["/path/to/attachment"]

on run argv
    set recipientAddress to item 1 of argv
    set emailSubject to item 2 of argv
    set emailBody to item 3 of argv

    -- Optional attachment path (4th argument)
    set attachmentPath to missing value
    if (count of argv) > 3 then
        set attachmentPath to item 4 of argv
    end if

    tell application "Mail"
        set newMessage to make new outgoing message with properties {subject:emailSubject, content:emailBody, visible:false}

        tell newMessage
            make new to recipient at end of to recipients with properties {address:recipientAddress}

            -- Add attachment if provided
            if attachmentPath is not missing value and attachmentPath is not "" then
                set attachmentFile to POSIX file attachmentPath
                try
                    make new attachment with properties {file name:attachmentFile} at after the last paragraph
                end try
            end if
        end tell

        send newMessage
    end tell

    return "Email sent successfully"
end run
